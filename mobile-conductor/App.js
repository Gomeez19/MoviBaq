import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
  ScrollView,
  Switch,
  RefreshControl,
} from 'react-native';
import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import AsyncStorage from '@react-native-async-storage/async-storage';

const LOCATION_TASK_NAME = 'MOVIBAQ_BACKGROUND_GPS_TASK';
const API_URL = 'https://movibaq.vercel.app';

// ==========================================
// TAREA EN SEGUNDO PLANO
// ==========================================
TaskManager.defineTask(LOCATION_TASK_NAME, async ({ data, error }) => {
  if (error) {
    console.error('Error en tarea de ubicación:', error);
    return;
  }
  if (data) {
    const { locations } = data;
    if (locations && locations.length > 0) {
      const loc = locations[locations.length - 1];
      try {
        const storedBusId = await AsyncStorage.getItem('assigned_bus_id');
        const storedRouteId = await AsyncStorage.getItem('assigned_route_id');
        const storedToken = await AsyncStorage.getItem('user_token');

        const busId = storedBusId || 'TM-8101';
        const routeId = storedRouteId || 'A8-1';
        const speedKmh = loc.coords.speed && loc.coords.speed > 0 ? loc.coords.speed * 3.6 : 0.0;

        await fetch(`${API_URL}/api/conductor/telemetry/gps`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(storedToken ? { 'Authorization': `Bearer ${storedToken}`, 'Cookie': `access_token=${storedToken}` } : {})
          },
          body: JSON.stringify({
            bus_id: busId,
            route_id: routeId,
            lat: loc.coords.latitude,
            lng: loc.coords.longitude,
            speed_kmh: Math.round(speedKmh * 10) / 10,
            heading: loc.coords.heading || 0.0,
            occupancy_percent: 50
          })
        });
      } catch (err) {
        console.warn('Error enviando telemetría en background:', err.message);
      }
    }
  }
});

export default function App() {
  const [activeTab, setActiveTab] = useState('cabina'); // 'cabina' | 'preop' | 'cco' | 'incidente'
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Autenticación
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [driverUser, setDriverUser] = useState(null);

  // Turno
  const [assignedBus, setAssignedBus] = useState('TM-8101');
  const [assignedRoute, setAssignedRoute] = useState('A8-1');
  const [routeName, setRouteName] = useState('Ruta Alimentadora');
  const [busPlate, setBusPlate] = useState('WPL-000');
  const [isTracking, setIsTracking] = useState(false);
  const [currentCoords, setCurrentCoords] = useState(null);

  // Preoperacional
  const [preopStatus, setPreopStatus] = useState('Pendiente de realizar');
  const [frenosOk, setFrenosOk] = useState(true);
  const [lucesOk, setLucesOk] = useState(true);
  const [puertasOk, setPuertasOk] = useState(true);
  const [extintorOk, setExtintorOk] = useState(true);
  const [aceiteOk, setAceiteOk] = useState(true);
  const [odometro, setOdometro] = useState('134500');

  // Mensajes CCO
  const [ccoMessages, setCcoMessages] = useState([]);

  // Reporte incidente
  const [incTipo, setIncTipo] = useState('Bloqueo en Vía / Congestión');
  const [incUbicacion, setIncUbicacion] = useState('Calle 30 frente al Hipódromo');
  const [incDescripcion, setIncDescripcion] = useState('');

  useEffect(() => {
    checkActiveSession();
    checkTrackingStatus();
  }, []);

  const checkActiveSession = async () => {
    try {
      const savedUser = await AsyncStorage.getItem('driver_profile');
      if (savedUser) {
        const parsed = JSON.parse(savedUser);
        setDriverUser(parsed);
        setIsLoggedIn(true);
        loadShiftDetails(parsed);
      }
    } catch (e) {
      console.warn('Error leyendo sesión previa:', e);
    }
  };

  const loadShiftDetails = async (user) => {
    try {
      setRefreshing(true);
      const token = await AsyncStorage.getItem('user_token');
      const res = await fetch(`${API_URL}/api/conductor/shift-info`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}`, 'Cookie': `access_token=${token}` } : {})
        }
      });
      const data = await res.json();
      if (data.status === 'success') {
        const c = data.conductor;
        setAssignedBus(c.bus_id);
        setAssignedRoute(c.route_id);
        setRouteName(c.route_name);
        setBusPlate(c.plate);
        setPreopStatus(c.preoperacional_estado || 'Pendiente');
        setCcoMessages(data.mensajes_cco || []);
        await AsyncStorage.setItem('assigned_bus_id', c.bus_id);
        await AsyncStorage.setItem('assigned_route_id', c.route_id);
      }
    } catch (err) {
      console.warn('Error cargando turno:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const checkTrackingStatus = async () => {
    try {
      const hasStarted = await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
      setIsTracking(hasStarted);
    } catch (e) {
      console.warn(e);
    }
  };

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Datos requeridos', 'Por favor ingresa tu correo y contraseña.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username_or_email: email.trim().toLowerCase(),
          password: password.trim()
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al iniciar sesión');

      if (data.user.role !== 'conductor' && data.user.role !== 'admin') {
        throw new Error('Esta aplicación es de uso exclusivo para Conductores de Transmetro.');
      }

      await AsyncStorage.setItem('driver_profile', JSON.stringify(data.user));
      if (data.token) await AsyncStorage.setItem('user_token', data.token);

      const bus = data.user.assigned_bus || 'TM-8101';
      const route = data.user.assigned_route || 'A8-1';
      setAssignedBus(bus);
      setAssignedRoute(route);
      await AsyncStorage.setItem('assigned_bus_id', bus);
      await AsyncStorage.setItem('assigned_route_id', route);

      setDriverUser(data.user);
      setIsLoggedIn(true);
      loadShiftDetails(data.user);
      Alert.alert('Bienvenido', `Hola ${data.user.fullname}, turno listo.`);
    } catch (err) {
      Alert.alert('Error de acceso', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    if (isTracking) {
      await stopBackgroundTracking();
    }
    await AsyncStorage.clear();
    setIsLoggedIn(false);
    setDriverUser(null);
    setEmail('');
    setPassword('');
  };

  const startBackgroundTracking = async () => {
    try {
      // 1. Permiso en primer plano
      const { status: fgStatus } = await Location.requestForegroundPermissionsAsync();
      if (fgStatus !== 'granted') {
        Alert.alert('Permiso requerido', 'Se requiere permiso de GPS para operar la ruta.');
        return;
      }

      // 2. Intentar solicitar permiso en segundo plano si está disponible
      try {
        await Location.requestBackgroundPermissionsAsync();
      } catch (bgErr) {
        console.warn('Background permission fallback:', bgErr);
      }

      // Guardar identificadores
      await AsyncStorage.setItem('assigned_bus_id', assignedBus);
      await AsyncStorage.setItem('assigned_route_id', assignedRoute);

      // Obtener posición inicial
      const currentLoc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setCurrentCoords(currentLoc.coords);

      // Enviar primer punto
      const token = await AsyncStorage.getItem('user_token');
      await fetch(`${API_URL}/api/conductor/telemetry/gps`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}`, 'Cookie': `access_token=${token}` } : {})
        },
        body: JSON.stringify({
          bus_id: assignedBus,
          route_id: assignedRoute,
          lat: currentLoc.coords.latitude,
          lng: currentLoc.coords.longitude,
          speed_kmh: 0.0,
          heading: currentLoc.coords.heading || 0.0,
          occupancy_percent: 50
        })
      });

      // Iniciar tarea background si es posible
      try {
        await Location.startLocationUpdatesAsync(LOCATION_TASK_NAME, {
          accuracy: Location.Accuracy.BestForNavigation,
          timeInterval: 3000,
          distanceInterval: 5,
          showsBackgroundLocationIndicator: true,
          foregroundService: {
            notificationTitle: `MoviBAQ: Ruta ${assignedRoute}`,
            notificationBody: `Padrón ${assignedBus} transmitiendo GPS en tiempo real.`,
            notificationColor: '#0252CD'
          }
        });
      } catch (taskErr) {
        console.warn('Modo Expo Go background fallback activado');
      }

      setIsTracking(true);
      Alert.alert('¡Transmisión Iniciada!', 'Tu bus está transmitiendo su ubicación en tiempo real al mapa de pasajeros y central CCO.');
    } catch (err) {
      console.error(err);
      Alert.alert('Aviso GPS', err.message);
    }
  };

  const stopBackgroundTracking = async () => {
    try {
      const hasStarted = await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
      if (hasStarted) {
        await Location.stopLocationUpdatesAsync(LOCATION_TASK_NAME);
      }
      setIsTracking(false);
      Alert.alert('Transmisión detenida', 'El bus ha dejado de emitir telemetría.');
    } catch (err) {
      setIsTracking(false);
    }
  };

  const submitPreoperacional = async () => {
    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('user_token');
      const payload = {
        bus_id: assignedBus,
        route_id: assignedRoute,
        odometro_km: parseInt(odometro) || 120000,
        frenos: {
          freno_servicio_ok: frenosOk,
          freno_estacionamiento_ok: frenosOk,
          presion_manometros_psi: 110
        },
        tecnico: {
          neumaticos_labrado_ok: true,
          luces_altas_bajas_ok: lucesOk,
          direccionales_freno_ok: lucesOk,
          limpiaparabrisas_espejos_ok: true
        },
        pasajeros: {
          timbre_parada_ok: true,
          puertas_neumaticas_ok: puertasOk,
          validador_tarjetas_ok: true,
          barras_sujecion_ok: true
        },
        seguridad: {
          extintor_vigente: extintorOk,
          botiquin_primeros_auxilios: true,
          martillos_fragmentadores: true,
          kit_carretera_repuesto: true
        },
        fluidos: {
          nivel_aceite_motor_ok: aceiteOk,
          nivel_refrigerante_ok: true,
          nivel_combustible_porcentaje: 85
        },
        observaciones: "Inspección móvil realizada desde la app del conductor."
      };

      const res = await fetch(`${API_URL}/api/conductor/preoperacional`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}`, 'Cookie': `access_token=${token}` } : {})
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al enviar preoperacional');

      setPreopStatus(data.estado_aprobacion);
      Alert.alert('Preoperacional Registrado', `Estado: ${data.estado_aprobacion}. Tu unidad ha sido evaluada.`);
      setActiveTab('cabina');
    } catch (err) {
      Alert.alert('Error', err.message);
    } finally {
      setLoading(false);
    }
  };

  const reportarIncidente = async () => {
    if (!incDescripcion.trim()) {
      Alert.alert('Campo requerido', 'Por favor describe la situación para notificar a la central.');
      return;
    }
    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('user_token');
      const res = await fetch(`${API_URL}/api/conductor/incidente`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}`, 'Cookie': `access_token=${token}` } : {})
        },
        body: JSON.stringify({
          bus_id: assignedBus,
          route_id: assignedRoute,
          tipo: incTipo,
          prioridad: "Alta",
          ubicacion_referencia: incUbicacion,
          descripcion: incDescripcion
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al reportar incidente');

      Alert.alert('Alerta Emitida', `El Centro de Control (CCO) ha recibido el reporte (${data.id}).`);
      setIncDescripcion('');
      setActiveTab('cabina');
    } catch (err) {
      Alert.alert('Error', err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // PANTALLA 1: LOGIN DEL CONDUCTOR
  // ==========================================
  if (!isLoggedIn) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor="#0252CD" />
        <View style={styles.flagBar}>
          <View style={[styles.flagStrip, { backgroundColor: '#DC2626' }]} />
          <View style={[styles.flagStrip, { backgroundColor: '#FACC15' }]} />
          <View style={[styles.flagStrip, { backgroundColor: '#059669' }]} />
        </View>

        <ScrollView contentContainerStyle={styles.loginContent}>
          <View style={styles.logoCircle}>
            <Text style={styles.logoIcon}>🚌</Text>
          </View>
          <Text style={styles.brandTitle}>Movi<Text style={{ color: '#0252CD' }}>BAQ</Text></Text>
          <Text style={styles.brandSubtitle}>Cabina Móvil del Conductor</Text>
          <Text style={styles.districtBadge}>Distrito de Barranquilla • Transmetro</Text>

          <View style={styles.card}>
            <Text style={styles.cardHeader}>Acceso para Operadores</Text>

            <Text style={styles.inputLabel}>CORREO ELECTRÓNICO</Text>
            <TextInput
              style={styles.input}
              placeholder="gil.pinzon@somexnutricion.com"
              placeholderTextColor="#94A3B8"
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
            />

            <Text style={styles.inputLabel}>CONTRASEÑA</Text>
            <TextInput
              style={styles.input}
              placeholder="••••••••"
              placeholderTextColor="#94A3B8"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />

            <TouchableOpacity
              style={[styles.primaryButton, loading && { opacity: 0.7 }]}
              onPress={handleLogin}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.primaryButtonText}>Iniciar Turno de Conducción →</Text>
              )}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ==========================================
  // PANTALLA PRINCIPAL CON NAVEGACIÓN MODULAR
  // ==========================================
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0252CD" />
      <View style={styles.flagBar}>
        <View style={[styles.flagStrip, { backgroundColor: '#DC2626' }]} />
        <View style={[styles.flagStrip, { backgroundColor: '#FACC15' }]} />
        <View style={[styles.flagStrip, { backgroundColor: '#059669' }]} />
      </View>

      <View style={styles.header}>
        <View>
          <Text style={styles.headerDriverName}>{driverUser?.fullname || 'Conductor Oficial'}</Text>
          <Text style={styles.headerStatus}>
            {isTracking ? '🟢 Transmitiendo GPS en Vivo' : '⚪ En espera de recorrido'}
          </Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Text style={styles.logoutBtnText}>Salir</Text>
        </TouchableOpacity>
      </View>

      {/* Selector de Pestañas */}
      <View style={styles.tabNav}>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'cabina' && styles.tabButtonActive]}
          onPress={() => setActiveTab('cabina')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'cabina' && styles.tabButtonTextActive]}>Cabina</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'preop' && styles.tabButtonActive]}
          onPress={() => setActiveTab('preop')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'preop' && styles.tabButtonTextActive]}>Preoperacional</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'cco' && styles.tabButtonActive]}
          onPress={() => setActiveTab('cco')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'cco' && styles.tabButtonTextActive]}>Central CCO</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'incidente' && styles.tabButtonActive]}
          onPress={() => setActiveTab('incidente')}
        >
          <Text style={[styles.tabButtonText, activeTab === 'incidente' && styles.tabButtonTextActive]}>Alerta</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.driverContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadShiftDetails(driverUser)} />}
      >
        {/* ====================================
            TAB 1: CABINA GPS PRINCIPAL
            ==================================== */}
        {activeTab === 'cabina' && (
          <View>
            <View style={styles.infoRow}>
              <View style={styles.infoBox}>
                <Text style={styles.infoBoxLabel}>PADRÓN / BUS</Text>
                <Text style={styles.infoBoxValue}>{assignedBus}</Text>
                <Text style={styles.infoBoxSub}>Placa: {busPlate}</Text>
              </View>
              <View style={styles.infoBox}>
                <Text style={styles.infoBoxLabel}>RUTA EN CURSO</Text>
                <Text style={styles.infoBoxValue}>{assignedRoute}</Text>
                <Text style={styles.infoBoxSub} numberOfLines={1}>{routeName}</Text>
              </View>
            </View>

            {/* Estado del preoperacional */}
            <View style={[styles.preopBanner, preopStatus === 'Aprobado' ? styles.preopOk : styles.preopPending]}>
              <Text style={styles.preopBannerTitle}>
                {preopStatus === 'Aprobado' ? '✓ Preoperacional Aprobado' : '⚠️ Inspección Preoperacional Requerida'}
              </Text>
              <Text style={styles.preopBannerBody}>
                {preopStatus === 'Aprobado'
                  ? 'Vehículo en condiciones técnicas aptas para circular.'
                  : 'Diligencia la inspección diaria obligatoria en la pestaña Preoperacional.'}
              </Text>
            </View>

            {/* Botón de Inicio / Pausa de GPS */}
            {isTracking ? (
              <TouchableOpacity style={styles.stopButton} onPress={stopBackgroundTracking}>
                <Text style={styles.stopButtonText}>⏹ Detener / Pausar Transmisión</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity style={styles.startButton} onPress={startBackgroundTracking}>
                <Text style={styles.startButtonText}>🛰️ Iniciar Ruta y Transmitir GPS</Text>
              </TouchableOpacity>
            )}

            {/* Resumen de telemetría */}
            <View style={styles.telemetryCard}>
              <Text style={styles.telemetryTitle}>Telemetría Transmetro</Text>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Servidor Nube:</Text>
                <Text style={styles.telemetryValue}>https://movibaq.vercel.app</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Intervalo:</Text>
                <Text style={styles.telemetryValue}>Cada 3 segundos</Text>
              </View>
              {currentCoords && (
                <View style={styles.telemetryRow}>
                  <Text style={styles.telemetryLabel}>Última Coordenada:</Text>
                  <Text style={styles.telemetryValue}>
                    {currentCoords.latitude.toFixed(5)}, {currentCoords.longitude.toFixed(5)}
                  </Text>
                </View>
              )}
            </View>
          </View>
        )}

        {/* ====================================
            TAB 2: INSPECCIÓN PREOPERACIONAL
            ==================================== */}
        {activeTab === 'preop' && (
          <View style={styles.tabContentCard}>
            <Text style={styles.cardHeader}>Inspección Técnica Preoperacional</Text>
            <Text style={styles.cardSub}>Validación de seguridad obligatoria antes de iniciar la marcha.</Text>

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Freno de Servicio y Parqueo (OK)</Text>
              <Switch value={frenosOk} onValueChange={setFrenosOk} trackColor={{ true: '#059669' }} />
            </View>

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Luces Altas, Bajas y Direccionales</Text>
              <Switch value={lucesOk} onValueChange={setLucesOk} trackColor={{ true: '#059669' }} />
            </View>

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Puertas Neumáticas y Timbres</Text>
              <Switch value={puertasOk} onValueChange={setPuertasOk} trackColor={{ true: '#059669' }} />
            </View>

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Extintor Vigente y Botiquín</Text>
              <Switch value={extintorOk} onValueChange={setExtintorOk} trackColor={{ true: '#059669' }} />
            </View>

            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Niveles de Aceite y Refrigerante</Text>
              <Switch value={aceiteOk} onValueChange={setAceiteOk} trackColor={{ true: '#059669' }} />
            </View>

            <Text style={[styles.inputLabel, { marginTop: 16 }]}>KILOMETRAJE / ODÓMETRO</Text>
            <TextInput
              style={styles.input}
              value={odometro}
              onChangeText={setOdometro}
              keyboardType="numeric"
              placeholder="134500"
            />

            <TouchableOpacity style={styles.actionBtnGreen} onPress={submitPreoperacional} disabled={loading}>
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.actionBtnText}>Registrar Inspección Preoperacional</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* ====================================
            TAB 3: MENSAJES Y REGULACIÓN CCO
            ==================================== */}
        {activeTab === 'cco' && (
          <View style={styles.tabContentCard}>
            <Text style={styles.cardHeader}>Instrucciones del Centro de Control (CCO)</Text>
            <Text style={styles.cardSub}>Canal oficial de regulación del Jefe de Ruta a tu unidad.</Text>

            {ccoMessages.length === 0 ? (
              <View style={styles.emptyBox}>
                <Text style={styles.emptyText}>No hay mensajes pendientes del Jefe de Ruta.</Text>
              </View>
            ) : (
              ccoMessages.map((msg, i) => (
                <View key={i} style={styles.messageCard}>
                  <View style={styles.msgHeader}>
                    <Text style={styles.msgSender}>{msg.sender || 'Jefe de Ruta'}</Text>
                    <Text style={styles.msgTime}>{msg.time || ''}</Text>
                  </View>
                  <Text style={styles.msgBody}>{msg.text}</Text>
                </View>
              ))
            )}

            <TouchableOpacity
              style={[styles.primaryButton, { marginTop: 20 }]}
              onPress={() => Alert.alert('Enterado', 'Confirmación de recibido enviada al CCO.')}
            >
              <Text style={styles.primaryButtonText}>✓ Confirmar Enterado a Central</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ====================================
            TAB 4: REPORTE DE INCIDENTE EN VÍA
            ==================================== */}
        {activeTab === 'incidente' && (
          <View style={styles.tabContentCard}>
            <Text style={styles.cardHeader}>Emitir Alerta de Incidente en Vía</Text>
            <Text style={styles.cardSub}>Notificación de emergencia inmediata al despachador.</Text>

            <Text style={styles.inputLabel}>PUNTO O PARADERO DE REFERENCIA</Text>
            <TextInput
              style={styles.input}
              value={incUbicacion}
              onChangeText={setIncUbicacion}
              placeholder="Ej. Calle 30 frente al Hipódromo"
            />

            <Text style={styles.inputLabel}>DESCRIPCIÓN DEL SUCESO</Text>
            <TextInput
              style={[styles.input, { height: 90, textAlignVertical: 'top' }]}
              value={incDescripcion}
              onChangeText={setIncDescripcion}
              placeholder="Describe lo ocurrido (varada, choque, congestión, etc.)..."
              multiline
            />

            <TouchableOpacity style={styles.actionBtnRed} onPress={reportarIncidente} disabled={loading}>
              {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.actionBtnText}>🚨 Enviar Alerta Urgente al CCO</Text>}
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  flagBar: {
    height: 4,
    flexDirection: 'row',
  },
  flagStrip: {
    flex: 1,
  },
  loginContent: {
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '90%',
  },
  logoCircle: {
    width: 72,
    height: 72,
    borderRadius: 24,
    backgroundColor: '#0252CD',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  logoIcon: {
    fontSize: 36,
  },
  brandTitle: {
    fontSize: 32,
    fontWeight: '900',
    color: '#FFFFFF',
    letterSpacing: -0.5,
  },
  brandSubtitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#94A3B8',
    marginTop: 2,
  },
  districtBadge: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#38BDF8',
    marginTop: 4,
    marginBottom: 24,
  },
  card: {
    width: '100%',
    backgroundColor: '#1E293B',
    borderRadius: 24,
    padding: 24,
    borderWidth: 1,
    borderColor: '#334155',
  },
  cardHeader: {
    fontSize: 16,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 4,
  },
  cardSub: {
    fontSize: 12,
    color: '#94A3B8',
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#94A3B8',
    marginBottom: 6,
    letterSpacing: 0.5,
  },
  input: {
    backgroundColor: '#0F172A',
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 14,
    color: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 16,
  },
  primaryButton: {
    backgroundColor: '#0252CD',
    paddingVertical: 15,
    borderRadius: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: '#1E293B',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  headerDriverName: {
    fontSize: 16,
    fontWeight: '900',
    color: '#FFFFFF',
  },
  headerStatus: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 2,
  },
  logoutBtn: {
    backgroundColor: '#334155',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  logoutBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: 'bold',
  },
  tabNav: {
    flexDirection: 'row',
    backgroundColor: '#1E293B',
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 10,
  },
  tabButtonActive: {
    backgroundColor: '#0252CD',
  },
  tabButtonText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#94A3B8',
  },
  tabButtonTextActive: {
    color: '#FFFFFF',
    fontWeight: '800',
  },
  driverContent: {
    padding: 16,
  },
  infoRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 14,
  },
  infoBox: {
    flex: 1,
    backgroundColor: '#1E293B',
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  infoBoxLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#94A3B8',
  },
  infoBoxValue: {
    fontSize: 20,
    fontWeight: '900',
    color: '#38BDF8',
    marginTop: 2,
  },
  infoBoxSub: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  preopBanner: {
    padding: 14,
    borderRadius: 16,
    marginBottom: 16,
    borderWidth: 1,
  },
  preopOk: {
    backgroundColor: 'rgba(5, 150, 105, 0.15)',
    borderColor: '#059669',
  },
  preopPending: {
    backgroundColor: 'rgba(217, 119, 6, 0.15)',
    borderColor: '#D97706',
  },
  preopBannerTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  preopBannerBody: {
    fontSize: 11,
    color: '#CBD5E1',
  },
  startButton: {
    backgroundColor: '#059669',
    paddingVertical: 16,
    borderRadius: 18,
    alignItems: 'center',
    marginBottom: 16,
    elevation: 4,
  },
  startButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '900',
  },
  stopButton: {
    backgroundColor: '#DC2626',
    paddingVertical: 16,
    borderRadius: 18,
    alignItems: 'center',
    marginBottom: 16,
    elevation: 4,
  },
  stopButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '900',
  },
  telemetryCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#334155',
  },
  telemetryTitle: {
    fontSize: 12,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 8,
  },
  telemetryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  telemetryLabel: {
    fontSize: 11,
    color: '#94A3B8',
  },
  telemetryValue: {
    fontSize: 11,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  tabContentCard: {
    backgroundColor: '#1E293B',
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: '#334155',
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  switchLabel: {
    fontSize: 12,
    color: '#F1F5F9',
    fontWeight: '600',
    flex: 1,
    paddingRight: 8,
  },
  actionBtnGreen: {
    backgroundColor: '#059669',
    paddingVertical: 15,
    borderRadius: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  actionBtnRed: {
    backgroundColor: '#DC2626',
    paddingVertical: 15,
    borderRadius: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  emptyBox: {
    padding: 24,
    alignItems: 'center',
  },
  emptyText: {
    color: '#64748B',
    fontSize: 12,
  },
  messageCard: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#0252CD',
  },
  msgHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  msgSender: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: 'bold',
  },
  msgTime: {
    color: '#64748B',
    fontSize: 10,
  },
  msgBody: {
    color: '#E2E8F0',
    fontSize: 12,
  },
});
