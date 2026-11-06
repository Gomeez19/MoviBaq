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
} from 'react-native';
import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import AsyncStorage from '@react-native-async-storage/async-storage';

const LOCATION_TASK_NAME = 'MOVIBAQ_BACKGROUND_GPS_TASK';
const API_URL = 'https://movi-baq.vercel.app'; // URL en la nube Vercel

// ==========================================
// TAREA EN SEGUNDO PLANO (ESTILO INDRIVER/UBER)
// Corre en el hilo del sistema operativo incluso con la app cerrada o pantalla apagada
// ==========================================
TaskManager.defineTask(LOCATION_TASK_NAME, async ({ data, error }) => {
  if (error) {
    console.error('Error en tarea de ubicación en segundo plano:', error);
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
            ...(storedToken ? { 'Cookie': `access_token=${storedToken}` } : {})
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
        console.warn('Fallo enviando telemetría en segundo plano:', err.message);
      }
    }
  }
});

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [driverUser, setDriverUser] = useState(null);

  // Estados de turno
  const [assignedBus, setAssignedBus] = useState('TM-8101');
  const [assignedRoute, setAssignedRoute] = useState('A8-1');
  const [isTracking, setIsTracking] = useState(false);
  const [currentCoords, setCurrentCoords] = useState(null);

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
        if (parsed.assigned_bus) setAssignedBus(parsed.assigned_bus);
        if (parsed.assigned_route) setAssignedRoute(parsed.assigned_route);
      }
    } catch (e) {
      console.warn('Error leyendo sesión previa:', e);
    }
  };

  const checkTrackingStatus = async () => {
    const hasStarted = await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
    setIsTracking(hasStarted);
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
      // 1. Permiso de ubicación en primer plano
      const { status: foregroundStatus } = await Location.requestForegroundPermissionsAsync();
      if (foregroundStatus !== 'granted') {
        Alert.alert('Permiso denegado', 'Se requiere permiso de GPS para operar la ruta.');
        return;
      }

      // 2. Permiso en segundo plano (estilo inDriver)
      const { status: backgroundStatus } = await Location.requestBackgroundPermissionsAsync();
      if (backgroundStatus !== 'granted') {
        Alert.alert(
          'Ubicación en segundo plano requerida',
          'Para que el GPS no se corte al bloquear la pantalla o abrir otra app, selecciona "Permitir siempre" en los ajustes de ubicación.'
        );
      }

      // Guardar identificadores en storage
      await AsyncStorage.setItem('assigned_bus_id', assignedBus);
      await AsyncStorage.setItem('assigned_route_id', assignedRoute);

      // 3. Registrar el servicio en segundo plano
      await Location.startLocationUpdatesAsync(LOCATION_TASK_NAME, {
        accuracy: Location.Accuracy.BestForNavigation,
        timeInterval: 3000, // Cada 3 segundos
        distanceInterval: 5,  // O cada 5 metros
        deferredUpdatesInterval: 3000,
        showsBackgroundLocationIndicator: true, // Píldora verde/azul en iOS
        foregroundService: {
          notificationTitle: `MoviBAQ: Ruta ${assignedRoute}`,
          notificationBody: `Padrón ${assignedBus} transmitiendo GPS en tiempo real a los pasajeros.`,
          notificationColor: '#0252CD'
        }
      });

      // Obtener coordenada inicial
      const currentLoc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setCurrentCoords(currentLoc.coords);

      setIsTracking(true);
      Alert.alert('¡Transmisión en Vivo Iniciada!', 'Tu bus está transmitiendo su ubicación en tiempo real. Puedes minimizar la app o apagar la pantalla.');
    } catch (err) {
      console.error(err);
      Alert.alert('Error al iniciar ruta', err.message);
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
      Alert.alert('Error al detener', err.message);
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

          <Text style={styles.footerNote}>Sistema conectado en vivo a la nube MoviBAQ.</Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ==========================================
  // PANTALLA 2: CABINA EN VIVO Y CONTROL GPS
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
            {isTracking ? '🟢 Transmitiendo GPS en segundo plano' : '⚪ En espera de iniciar recorrido'}
          </Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Text style={styles.logoutBtnText}>Salir</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.driverContent}>
        {/* Tarjetas de Datos de la Unidad */}
        <View style={styles.infoRow}>
          <View style={styles.infoBox}>
            <Text style={styles.infoBoxLabel}>PADRÓN / BUS</Text>
            <Text style={styles.infoBoxValue}>{assignedBus}</Text>
          </View>
          <View style={styles.infoBox}>
            <Text style={styles.infoBoxLabel}>RUTA EN CURSO</Text>
            <Text style={styles.infoBoxValue}>{assignedRoute}</Text>
          </View>
        </View>

        {/* Banner de Modo Segundo Plano */}
        <View style={styles.bgNotice}>
          <Text style={styles.bgNoticeTitle}>🛡️ Operación en Segundo Plano Activa</Text>
          <Text style={styles.bgNoticeBody}>
            Esta aplicación continuará enviando tus coordenadas aunque bloquees el celular, contestes llamadas o abras otra app.
          </Text>
        </View>

        {/* Botón Principal de Acción */}
        {isTracking ? (
          <TouchableOpacity style={styles.stopButton} onPress={stopBackgroundTracking}>
            <Text style={styles.stopButtonText}>⏹ Detener / Pausar Transmisión</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={styles.startButton} onPress={startBackgroundTracking}>
            <Text style={styles.startButtonText}>🛰️ Iniciar Ruta y Transmitir GPS</Text>
          </TouchableOpacity>
        )}

        {/* Estado actual de telemetría */}
        <View style={styles.telemetryCard}>
          <Text style={styles.telemetryTitle}>Estado de Telemetría</Text>
          <View style={styles.telemetryRow}>
            <Text style={styles.telemetryLabel}>Frecuencia de emisión:</Text>
            <Text style={styles.telemetryValue}>Cada 3 segundos</Text>
          </View>
          <View style={styles.telemetryRow}>
            <Text style={styles.telemetryLabel}>Servidor en la Nube:</Text>
            <Text style={styles.telemetryValue}>Conectado (Vercel/Neon)</Text>
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
  footerNote: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 24,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
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
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 2,
  },
  logoutBtn: {
    backgroundColor: '#334155',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
  },
  logoutBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  driverContent: {
    padding: 20,
  },
  infoRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  infoBox: {
    flex: 1,
    backgroundColor: '#1E293B',
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#334155',
  },
  infoBoxLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#94A3B8',
  },
  infoBoxValue: {
    fontSize: 22,
    fontWeight: '900',
    color: '#38BDF8',
    marginTop: 4,
  },
  bgNotice: {
    backgroundColor: 'rgba(2, 82, 205, 0.15)',
    borderWidth: 1,
    borderColor: '#0252CD',
    padding: 16,
    borderRadius: 18,
    marginBottom: 20,
  },
  bgNoticeTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#60A5FA',
    marginBottom: 4,
  },
  bgNoticeBody: {
    fontSize: 12,
    color: '#CBD5E1',
    lineHeight: 18,
  },
  startButton: {
    backgroundColor: '#059669',
    paddingVertical: 18,
    borderRadius: 20,
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: '#059669',
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 6,
  },
  startButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
  },
  stopButton: {
    backgroundColor: '#DC2626',
    paddingVertical: 18,
    borderRadius: 20,
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: '#DC2626',
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 6,
  },
  stopButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
  },
  telemetryCard: {
    backgroundColor: '#1E293B',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  telemetryTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 12,
  },
  telemetryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  telemetryLabel: {
    fontSize: 12,
    color: '#94A3B8',
  },
  telemetryValue: {
    fontSize: 12,
    fontWeight: '700',
    color: '#F8FAFC',
  },
});
