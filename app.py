# """
# Cyber-Physical Guard - Unified Backend Server
# Combines fleet simulation, Kafka consumers, AI processing, and WebSocket broadcasting
# """

# import os
# import json
# import asyncio
# import time
# import io
# import random
# from datetime import datetime
# from dotenv import load_dotenv
# from confluent_kafka import Producer, Consumer
# import fastavro
# import google.generativeai as genai
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# import uvicorn

# load_dotenv()

# app = FastAPI(title="Cyber-Physical Guard")

# # Configuration
# KAFKA_BOOTSTRAP = os.getenv('CONFLUENT_BOOTSTRAP_SERVERS')
# KAFKA_KEY = os.getenv('CONFLUENT_API_KEY')
# KAFKA_SECRET = os.getenv('CONFLUENT_API_SECRET')
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# TELEMETRY_TOPIC = 'truck_telemetry'
# ALERTS_TOPIC = 'critical_alerts_json'

# # Avro schema for Flink alerts
# ALERT_SCHEMA = {
#     "type": "record",
#     "name": "critical_alerts_json",
#     "fields": [
#         {"name": "alert_level", "type": ["null", "string"], "default": None},
#         {"name": "alert_message", "type": ["null", "string"], "default": None},
#         {"name": "cargo", "type": ["null", "string"], "default": None},
#         {"name": "temp", "type": ["null", "double"], "default": None},
#         {"name": "timestamp", "type": ["null", "string"], "default": None},
#         {"name": "truck_id", "type": ["null", "string"], "default": None}
#     ]
# }
# PARSED_SCHEMA = fastavro.parse_schema(ALERT_SCHEMA)

# # Truck configurations
# TRUCK_CONFIG = {
#     'TRUCK_001': {'cargo': 'Vaccines', 'cargo_value': 250000, 'temp_optimal': 5, 'temp_critical': 12, 'lat': 32.7767, 'lng': -96.7970},
#     'TRUCK_002': {'cargo': 'Frozen Seafood', 'cargo_value': 85000, 'temp_optimal': -22, 'temp_critical': -15, 'lat': 29.7604, 'lng': -95.3698},
#     'TRUCK_003': {'cargo': 'Electronics', 'cargo_value': 175000, 'temp_optimal': 22, 'temp_critical': 40, 'lat': 32.4487, 'lng': -99.7331},
#     'TRUCK_004': {'cargo': 'Insulin', 'cargo_value': 320000, 'temp_optimal': 5, 'temp_critical': 12, 'lat': 30.2672, 'lng': -97.7431},
#     'TRUCK_005': {'cargo': 'Fresh Produce', 'cargo_value': 45000, 'temp_optimal': 3, 'temp_critical': 8, 'lat': 29.4241, 'lng': -98.4936},
# }

# # Auto demo schedule (cycle number -> truck to trigger)
# DEMO_SCHEDULE = {10: 'TRUCK_001', 25: 'TRUCK_004', 40: 'TRUCK_002', 55: 'TRUCK_005', 70: 'TRUCK_003'}


# class SystemState:
#     """Holds all application state"""
#     def __init__(self):
#         self.clients = set()
#         self.trucks = {}
#         self.alerts = []
#         self.logs = []
#         self.processed_alerts = {}
#         self.ai_calls = 0
#         self.gemini = None
#         self.producer = None
#         self.running = False
#         self.demo_mode = False
#         self.cycle = 0
#         self.truck_states = {}
        
#     def init_trucks(self):
#         for truck_id, cfg in TRUCK_CONFIG.items():
#             self.truck_states[truck_id] = {
#                 'is_critical': False,
#                 'temp': cfg['temp_optimal'],
#                 'speed': random.uniform(65, 80),
#                 'fuel': random.uniform(75, 95),
#                 'lat': cfg['lat'],
#                 'lng': cfg['lng']
#             }

# state = SystemState()


# def add_log(source, message):
#     """Add a log entry and broadcast to clients"""
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     entry = {"time": timestamp, "source": source, "message": message}
#     state.logs.append(entry)
#     if len(state.logs) > 200:
#         state.logs = state.logs[-200:]
#     asyncio.create_task(broadcast({"type": "log", "data": entry}))


# def init_gemini():
#     """Initialize Gemini AI model"""
#     if not GEMINI_API_KEY:
#         add_log("AI", "No GEMINI_API_KEY configured")
#         return None
    
#     genai.configure(api_key=GEMINI_API_KEY)
#     models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
#     for model_name in models_to_try:
#         try:
#             model = genai.GenerativeModel(model_name)
#             test = model.generate_content("OK")
#             if test.text:
#                 add_log("AI", f"Initialized {model_name}")
#                 return model
#         except Exception as e:
#             add_log("AI", f"{model_name} unavailable: {str(e)[:40]}")
    
#     return None


# def get_ai_recommendation(truck_id, cargo, temp, alert_msg, cargo_value):
#     """Generate AI recommendation for an alert"""
#     if not state.gemini:
#         return "AI service unavailable"
    
#     prompt = f"""Fleet alert - respond in exactly 4 lines:

# Truck: {truck_id} | Cargo: {cargo} (${cargo_value:,}) | Temp: {temp}C
# Alert: {alert_msg}

# Format:
# SEVERITY: [Critical/High] - reason
# ACTION: [specific action]
# URGENCY: [timeframe]
# NOTIFY: [who to contact]"""

#     try:
#         state.ai_calls += 1
#         response = state.gemini.generate_content(prompt)
#         return response.text
#     except Exception as e:
#         return f"AI error: {str(e)[:50]}"


# def decode_avro(data):
#     """Decode Confluent AVRO message"""
#     if len(data) < 5:
#         return None
#     if data[0] != 0:
#         try:
#             return json.loads(data.decode('utf-8'))
#         except:
#             return None
#     try:
#         reader = io.BytesIO(data[5:])
#         return fastavro.schemaless_reader(reader, PARSED_SCHEMA)
#     except:
#         return None


# def is_duplicate(truck_id, cargo):
#     """Check if alert was recently processed"""
#     key = f"{truck_id}_{cargo}"
#     now = time.time()
#     if key in state.processed_alerts:
#         if now - state.processed_alerts[key] < 30:
#             return True
#     state.processed_alerts[key] = now
#     return False


# async def broadcast(message):
#     """Send message to all connected WebSocket clients"""
#     if not state.clients:
#         return
    
#     msg_str = json.dumps(message, default=str)
#     disconnected = set()
    
#     for client in state.clients:
#         try:
#             await client.send_text(msg_str)
#         except:
#             disconnected.add(client)
    
#     state.clients -= disconnected


# def create_kafka_producer():
#     """Create Kafka producer"""
#     config = {
#         'bootstrap.servers': KAFKA_BOOTSTRAP,
#         'security.protocol': 'SASL_SSL',
#         'sasl.mechanisms': 'PLAIN',
#         'sasl.username': KAFKA_KEY,
#         'sasl.password': KAFKA_SECRET,
#     }
#     return Producer(config)


# def create_kafka_consumer(group_suffix):
#     """Create Kafka consumer"""
#     config = {
#         'bootstrap.servers': KAFKA_BOOTSTRAP,
#         'security.protocol': 'SASL_SSL',
#         'sasl.mechanisms': 'PLAIN',
#         'sasl.username': KAFKA_KEY,
#         'sasl.password': KAFKA_SECRET,
#         'group.id': f'cpg-unified-{group_suffix}',
#         'auto.offset.reset': 'latest'
#     }
#     return Consumer(config)


# async def simulator_loop():
#     """Fleet simulator - generates truck telemetry"""
#     add_log("SIMULATOR", "Starting fleet simulation")
#     state.producer = create_kafka_producer()
#     state.init_trucks()
    
#     while state.running:
#         state.cycle += 1
        
#         # Check demo schedule for auto-triggers
#         if state.demo_mode and state.cycle in DEMO_SCHEDULE:
#             truck_id = DEMO_SCHEDULE[state.cycle]
#             if not state.truck_states[truck_id]['is_critical']:
#                 state.truck_states[truck_id]['is_critical'] = True
#                 cfg = TRUCK_CONFIG[truck_id]
#                 state.truck_states[truck_id]['temp'] = cfg['temp_critical']
#                 add_log("SIMULATOR", f"[AUTO] {truck_id} set to CRITICAL")
        
#         # Reset cycle counter for demo mode loop
#         if state.demo_mode and state.cycle > 80:
#             state.cycle = 0
        
#         # Update and send telemetry for each truck
#         for truck_id, ts in state.truck_states.items():
#             cfg = TRUCK_CONFIG[truck_id]
            
#             # Update temperature
#             if ts['is_critical']:
#                 ts['temp'] = cfg['temp_critical'] + random.uniform(-0.3, 0.5)
#             else:
#                 ts['temp'] = cfg['temp_optimal'] + random.uniform(-0.3, 0.3)
            
#             # Update other values
#             ts['speed'] = random.uniform(60, 85)
#             ts['fuel'] = max(50, ts['fuel'] - random.uniform(0.01, 0.03))
#             ts['lat'] += random.uniform(-0.0005, 0.0005)
#             ts['lng'] += random.uniform(-0.0005, 0.0005)
            
#             status = 'critical' if ts['is_critical'] else 'normal'
            
#             telemetry = {
#                 'truck_id': truck_id,
#                 'timestamp': datetime.utcnow().isoformat() + 'Z',
#                 'cargo': cfg['cargo'],
#                 'cargo_value': cfg['cargo_value'],
#                 'temp': round(ts['temp'], 2),
#                 'speed': round(ts['speed'], 1),
#                 'speed_kmh': round(ts['speed'], 1),
#                 'fuel': round(ts['fuel'], 1),
#                 'fuel_level': round(ts['fuel'], 1),
#                 'lat': round(ts['lat'], 6),
#                 'lng': round(ts['lng'], 6),
#                 'status': status
#             }
            
#             state.trucks[truck_id] = telemetry
            
#             try:
#                 state.producer.produce(
#                     TELEMETRY_TOPIC,
#                     key=truck_id,
#                     value=json.dumps(telemetry)
#                 )
#             except Exception as e:
#                 add_log("SIMULATOR", f"Kafka error: {str(e)[:40]}")
            
#             await broadcast({'type': 'truck_update', 'data': telemetry})
        
#         state.producer.flush()
        
#         # Log status periodically
#         if state.cycle % 5 == 0:
#             critical_count = sum(1 for t in state.truck_states.values() if t['is_critical'])
#             add_log("SIMULATOR", f"Cycle {state.cycle} | {len(state.trucks)} trucks | {critical_count} critical")
        
#         await asyncio.sleep(2)
    
#     add_log("SIMULATOR", "Simulation stopped")


# async def telemetry_consumer_loop():
#     """Consume telemetry from Kafka and broadcast to clients"""
#     add_log("KAFKA", f"Subscribing to {TELEMETRY_TOPIC}")
#     consumer = create_kafka_consumer("telemetry")
#     consumer.subscribe([TELEMETRY_TOPIC])
    
#     while state.running:
#         msg = consumer.poll(0.1)
#         if msg is None:
#             await asyncio.sleep(0.05)
#             continue
#         if msg.error():
#             continue
        
#         try:
#             data = json.loads(msg.value().decode('utf-8'))
#             truck_id = data.get('truck_id')
#             if truck_id:
#                 state.trucks[truck_id] = data
#                 await broadcast({'type': 'truck_update', 'data': data})
#         except Exception as e:
#             add_log("KAFKA", f"Telemetry parse error: {str(e)[:30]}")
        
#         await asyncio.sleep(0.01)
    
#     consumer.close()


# async def alerts_consumer_loop():
#     """Consume alerts from Flink, generate AI recommendations"""
#     add_log("KAFKA", f"Subscribing to {ALERTS_TOPIC}")
#     consumer = create_kafka_consumer("alerts")
#     consumer.subscribe([ALERTS_TOPIC])
    
#     while state.running:
#         msg = consumer.poll(0.1)
#         if msg is None:
#             await asyncio.sleep(0.05)
#             continue
#         if msg.error():
#             continue
        
#         try:
#             data = decode_avro(msg.value())
#             if not data:
#                 continue
            
#             truck_id = data.get('truck_id')
#             cargo = data.get('cargo', 'Unknown')
            
#             if not truck_id:
#                 continue
            
#             if is_duplicate(truck_id, cargo):
#                 continue
            
#             temp = data.get('temp', 0)
#             alert_msg = data.get('alert_message', 'Temperature anomaly')
#             cargo_value = state.trucks.get(truck_id, {}).get('cargo_value', 0)
            
#             add_log("FLINK", f"Alert: {truck_id} - {cargo} at {temp}C")
            
#             # Generate AI recommendation
#             add_log("AI", f"Generating recommendation for {truck_id}...")
#             ai_start = time.time()
#             ai_rec = get_ai_recommendation(truck_id, cargo, temp, alert_msg, cargo_value)
#             ai_time = time.time() - ai_start
#             add_log("AI", f"Recommendation ready ({ai_time:.1f}s)")
            
#             alert = {
#                 'id': f"alert_{truck_id}_{int(time.time()*1000)}",
#                 'truck_id': truck_id,
#                 'cargo': cargo,
#                 'cargo_value': cargo_value,
#                 'temp': temp,
#                 'anomaly_type': 'TEMPERATURE_CRITICAL',
#                 'message': f"[Flink] {alert_msg}",
#                 'severity': 'critical',
#                 'timestamp': data.get('timestamp', datetime.now().isoformat()),
#                 'ai_recommendation': ai_rec
#             }
            
#             state.alerts.insert(0, alert)
#             if len(state.alerts) > 100:
#                 state.alerts = state.alerts[:100]
            
#             if truck_id in state.trucks:
#                 state.trucks[truck_id]['status'] = 'critical'
#                 await broadcast({'type': 'truck_update', 'data': state.trucks[truck_id]})
            
#             await broadcast({
#                 'type': 'alert',
#                 'data': alert,
#                 'stats': {'ai_calls': state.ai_calls, 'total_alerts': len(state.alerts)}
#             })
            
#             add_log("SERVER", f"Alert broadcast to {len(state.clients)} clients")
            
#         except Exception as e:
#             add_log("FLINK", f"Alert processing error: {str(e)[:40]}")
        
#         await asyncio.sleep(0.01)
    
#     consumer.close()


# @app.get("/")
# async def serve_dashboard():
#     """Serve the dashboard HTML"""
#     return FileResponse("static/index.html")


# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     """WebSocket connection handler"""
#     await websocket.accept()
#     state.clients.add(websocket)
#     add_log("SERVER", f"Client connected. Total: {len(state.clients)}")
    
#     try:
#         # Send initial state
#         await websocket.send_text(json.dumps({
#             'type': 'init',
#             'trucks': state.trucks,
#             'alerts': state.alerts[-30:],
#             'logs': state.logs[-50:],
#             'stats': {'ai_calls': state.ai_calls, 'total_alerts': len(state.alerts)},
#             'status': {'running': state.running, 'demo_mode': state.demo_mode}
#         }, default=str))
        
#         while True:
#             data = await websocket.receive_text()
#             msg = json.loads(data)
#             await handle_client_message(msg)
            
#     except WebSocketDisconnect:
#         state.clients.discard(websocket)
#         add_log("SERVER", f"Client disconnected. Total: {len(state.clients)}")


# async def handle_client_message(msg):
#     """Handle commands from dashboard"""
#     cmd = msg.get('command')
    
#     if cmd == 'start':
#         if not state.running:
#             state.running = True
#             state.demo_mode = msg.get('demo', False)
#             state.cycle = 0
#             state.init_trucks()
#             mode = "AUTOMATIC" if state.demo_mode else "MANUAL"
#             add_log("SERVER", f"Starting simulation in {mode} mode")
            
#             # Initialize AI
#             state.gemini = init_gemini()
            
#             # Start background tasks
#             asyncio.create_task(simulator_loop())
#             asyncio.create_task(alerts_consumer_loop())
            
#             await broadcast({'type': 'status', 'running': True, 'demo_mode': state.demo_mode})
    
#     elif cmd == 'stop':
#         if state.running:
#             state.running = False
#             add_log("SERVER", "Stopping simulation")
#             await broadcast({'type': 'status', 'running': False, 'demo_mode': False})
    
#     elif cmd == 'trigger':
#         truck_num = msg.get('truck')
#         if truck_num and 1 <= truck_num <= 5:
#             truck_id = f"TRUCK_00{truck_num}"
#             if truck_id in state.truck_states:
#                 if not state.truck_states[truck_id]['is_critical']:
#                     state.truck_states[truck_id]['is_critical'] = True
#                     cfg = TRUCK_CONFIG[truck_id]
#                     state.truck_states[truck_id]['temp'] = cfg['temp_critical']
#                     add_log("SIMULATOR", f"[MANUAL] {truck_id} ({cfg['cargo']}) set to CRITICAL")
    
#     elif cmd == 'reset':
#         for truck_id in state.truck_states:
#             state.truck_states[truck_id]['is_critical'] = False
#             cfg = TRUCK_CONFIG[truck_id]
#             state.truck_states[truck_id]['temp'] = cfg['temp_optimal']
#         add_log("SIMULATOR", "All trucks reset to NORMAL")


# @app.on_event("startup")
# async def startup():
#     """Initialize on server start"""
#     os.makedirs("static", exist_ok=True)
#     add_log("SERVER", "Cyber-Physical Guard server started")
#     add_log("SERVER", f"Kafka: {KAFKA_BOOTSTRAP[:30]}..." if KAFKA_BOOTSTRAP else "Kafka: Not configured")


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))




# """
# Cyber-Physical Guard - Unified Backend Server
# """

# import os
# import json
# import asyncio
# import time
# import io
# import random
# from datetime import datetime
# from dotenv import load_dotenv
# from confluent_kafka import Producer, Consumer
# import fastavro
# import google.generativeai as genai
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# import uvicorn

# load_dotenv()

# # Get the directory where app.py is located
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# STATIC_DIR = os.path.join(BASE_DIR, "static")

# # Ensure static directory exists
# os.makedirs(STATIC_DIR, exist_ok=True)

# app = FastAPI(title="Cyber-Physical Guard")

# # Mount static files with absolute path
# app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# KAFKA_BOOTSTRAP = os.getenv('CONFLUENT_BOOTSTRAP_SERVERS')
# KAFKA_KEY = os.getenv('CONFLUENT_API_KEY')
# KAFKA_SECRET = os.getenv('CONFLUENT_API_SECRET')
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# TELEMETRY_TOPIC = 'truck_telemetry'
# ALERTS_TOPIC = 'critical_alerts_json'

# ALERT_SCHEMA = {
#     "type": "record",
#     "name": "critical_alerts_json",
#     "fields": [
#         {"name": "alert_level", "type": ["null", "string"], "default": None},
#         {"name": "alert_message", "type": ["null", "string"], "default": None},
#         {"name": "cargo", "type": ["null", "string"], "default": None},
#         {"name": "temp", "type": ["null", "double"], "default": None},
#         {"name": "timestamp", "type": ["null", "string"], "default": None},
#         {"name": "truck_id", "type": ["null", "string"], "default": None}
#     ]
# }
# PARSED_SCHEMA = fastavro.parse_schema(ALERT_SCHEMA)

# TRUCK_CONFIG = {
#     'TRUCK_001': {'cargo': 'Vaccines', 'cargo_value': 250000, 'temp_optimal': 5, 'temp_critical': 12, 'lat': 32.7767, 'lng': -96.7970},
#     'TRUCK_002': {'cargo': 'Frozen Seafood', 'cargo_value': 85000, 'temp_optimal': -22, 'temp_critical': -15, 'lat': 29.7604, 'lng': -95.3698},
#     'TRUCK_003': {'cargo': 'Electronics', 'cargo_value': 175000, 'temp_optimal': 22, 'temp_critical': 40, 'lat': 32.4487, 'lng': -99.7331},
#     'TRUCK_004': {'cargo': 'Insulin', 'cargo_value': 320000, 'temp_optimal': 5, 'temp_critical': 12, 'lat': 30.2672, 'lng': -97.7431},
#     'TRUCK_005': {'cargo': 'Fresh Produce', 'cargo_value': 45000, 'temp_optimal': 3, 'temp_critical': 8, 'lat': 29.4241, 'lng': -98.4936},
# }

# DEMO_SCHEDULE = {10: 'TRUCK_001', 25: 'TRUCK_004', 40: 'TRUCK_002', 55: 'TRUCK_005', 70: 'TRUCK_003'}


# class SystemState:
#     def __init__(self):
#         self.clients = set()
#         self.trucks = {}
#         self.alerts = []
#         self.logs = []
#         self.processed_alerts = {}
#         self.ai_calls = 0
#         self.gemini = None
#         self.producer = None
#         self.running = False
#         self.demo_mode = False
#         self.cycle = 0
#         self.truck_states = {}
        
#     def init_trucks(self):
#         for truck_id, cfg in TRUCK_CONFIG.items():
#             self.truck_states[truck_id] = {
#                 'is_critical': False,
#                 'temp': cfg['temp_optimal'],
#                 'speed': random.uniform(65, 80),
#                 'fuel': random.uniform(75, 95),
#                 'lat': cfg['lat'],
#                 'lng': cfg['lng']
#             }

# state = SystemState()


# def add_log(source, message):
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     entry = {"time": timestamp, "source": source, "message": message}
#     state.logs.append(entry)
#     if len(state.logs) > 200:
#         state.logs = state.logs[-200:]
#     # Safe broadcast - handle case when no event loop is running
#     try:
#         loop = asyncio.get_running_loop()
#         asyncio.create_task(broadcast({"type": "log", "data": entry}))
#     except RuntimeError:
#         pass  # No event loop running yet (startup)


# def init_gemini():
#     if not GEMINI_API_KEY:
#         add_log("AI", "No GEMINI_API_KEY configured")
#         return None
    
#     genai.configure(api_key=GEMINI_API_KEY)
#     models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
#     for model_name in models_to_try:
#         try:
#             model = genai.GenerativeModel(model_name)
#             test = model.generate_content("OK")
#             if test.text:
#                 add_log("AI", f"Initialized {model_name}")
#                 return model
#         except Exception as e:
#             add_log("AI", f"{model_name} unavailable: {str(e)[:40]}")
    
#     return None


# def get_ai_recommendation(truck_id, cargo, temp, alert_msg, cargo_value):
#     if not state.gemini:
#         return "AI service unavailable"
    
#     prompt = f"""Fleet alert - respond in exactly 4 lines:

# Truck: {truck_id} | Cargo: {cargo} (${cargo_value:,}) | Temp: {temp}C
# Alert: {alert_msg}

# Format:
# SEVERITY: [Critical/High] - reason
# ACTION: [specific action]
# URGENCY: [timeframe]
# NOTIFY: [who to contact]"""

#     try:
#         state.ai_calls += 1
#         response = state.gemini.generate_content(prompt)
#         return response.text
#     except Exception as e:
#         return f"AI error: {str(e)[:50]}"


# def decode_avro(data):
#     if len(data) < 5:
#         return None
#     if data[0] != 0:
#         try:
#             return json.loads(data.decode('utf-8'))
#         except:
#             return None
#     try:
#         reader = io.BytesIO(data[5:])
#         return fastavro.schemaless_reader(reader, PARSED_SCHEMA)
#     except:
#         return None


# def is_duplicate(truck_id, cargo):
#     key = f"{truck_id}_{cargo}"
#     now = time.time()
#     if key in state.processed_alerts:
#         if now - state.processed_alerts[key] < 30:
#             return True
#     state.processed_alerts[key] = now
#     return False


# async def broadcast(message):
#     if not state.clients:
#         return
    
#     msg_str = json.dumps(message, default=str)
#     disconnected = set()
    
#     for client in state.clients:
#         try:
#             await client.send_text(msg_str)
#         except:
#             disconnected.add(client)
    
#     state.clients -= disconnected


# def create_kafka_producer():
#     if not KAFKA_BOOTSTRAP or not KAFKA_KEY or not KAFKA_SECRET:
#         raise Exception("Kafka credentials not configured")
#     config = {
#         'bootstrap.servers': KAFKA_BOOTSTRAP,
#         'security.protocol': 'SASL_SSL',
#         'sasl.mechanisms': 'PLAIN',
#         'sasl.username': KAFKA_KEY,
#         'sasl.password': KAFKA_SECRET,
#     }
#     return Producer(config)


# def create_kafka_consumer(group_suffix):
#     if not KAFKA_BOOTSTRAP or not KAFKA_KEY or not KAFKA_SECRET:
#         raise Exception("Kafka credentials not configured")
#     config = {
#         'bootstrap.servers': KAFKA_BOOTSTRAP,
#         'security.protocol': 'SASL_SSL',
#         'sasl.mechanisms': 'PLAIN',
#         'sasl.username': KAFKA_KEY,
#         'sasl.password': KAFKA_SECRET,
#         'group.id': f'cpg-unified-{group_suffix}',
#         'auto.offset.reset': 'latest'
#     }
#     return Consumer(config)


# async def simulator_loop():
#     add_log("SIMULATOR", "Starting fleet simulation")
    
#     try:
#         state.producer = create_kafka_producer()
#         add_log("KAFKA", "Producer connected")
#     except Exception as e:
#         add_log("SIMULATOR", f"Kafka producer error: {str(e)[:50]}")
#         return
    
#     state.init_trucks()
    
#     while state.running:
#         state.cycle += 1
        
#         if state.demo_mode and state.cycle in DEMO_SCHEDULE:
#             truck_id = DEMO_SCHEDULE[state.cycle]
#             if not state.truck_states[truck_id]['is_critical']:
#                 state.truck_states[truck_id]['is_critical'] = True
#                 cfg = TRUCK_CONFIG[truck_id]
#                 state.truck_states[truck_id]['temp'] = cfg['temp_critical']
#                 add_log("SIMULATOR", f"[AUTO] {truck_id} set to CRITICAL")
        
#         if state.demo_mode and state.cycle > 80:
#             state.cycle = 0
        
#         for truck_id, ts in state.truck_states.items():
#             cfg = TRUCK_CONFIG[truck_id]
            
#             if ts['is_critical']:
#                 ts['temp'] = cfg['temp_critical'] + random.uniform(-0.3, 0.5)
#             else:
#                 ts['temp'] = cfg['temp_optimal'] + random.uniform(-0.3, 0.3)
            
#             ts['speed'] = random.uniform(60, 85)
#             ts['fuel'] = max(50, ts['fuel'] - random.uniform(0.01, 0.03))
#             ts['lat'] += random.uniform(-0.0005, 0.0005)
#             ts['lng'] += random.uniform(-0.0005, 0.0005)
            
#             status = 'critical' if ts['is_critical'] else 'normal'
            
#             telemetry = {
#                 'truck_id': truck_id,
#                 'timestamp': datetime.utcnow().isoformat() + 'Z',
#                 'cargo': cfg['cargo'],
#                 'cargo_value': cfg['cargo_value'],
#                 'temp': round(ts['temp'], 2),
#                 'speed': round(ts['speed'], 1),
#                 'speed_kmh': round(ts['speed'], 1),
#                 'fuel': round(ts['fuel'], 1),
#                 'fuel_level': round(ts['fuel'], 1),
#                 'lat': round(ts['lat'], 6),
#                 'lng': round(ts['lng'], 6),
#                 'status': status
#             }
            
#             state.trucks[truck_id] = telemetry
            
#             try:
#                 state.producer.produce(
#                     TELEMETRY_TOPIC,
#                     key=truck_id,
#                     value=json.dumps(telemetry)
#                 )
#             except Exception as e:
#                 add_log("SIMULATOR", f"Kafka send error: {str(e)[:40]}")
            
#             await broadcast({'type': 'truck_update', 'data': telemetry})
        
#         try:
#             state.producer.flush(timeout=1)
#         except:
#             pass
        
#         if state.cycle % 5 == 0:
#             critical_count = sum(1 for t in state.truck_states.values() if t['is_critical'])
#             add_log("SIMULATOR", f"Cycle {state.cycle} | {len(state.trucks)} trucks | {critical_count} critical")
        
#         await asyncio.sleep(2)
    
#     add_log("SIMULATOR", "Simulation stopped")


# async def alerts_consumer_loop():
#     add_log("KAFKA", f"Subscribing to {ALERTS_TOPIC}")
    
#     try:
#         consumer = create_kafka_consumer("alerts")
#         consumer.subscribe([ALERTS_TOPIC])
#     except Exception as e:
#         add_log("KAFKA", f"Consumer error: {str(e)[:50]}")
#         return
    
#     while state.running:
#         msg = consumer.poll(0.1)
#         if msg is None:
#             await asyncio.sleep(0.05)
#             continue
#         if msg.error():
#             continue
        
#         try:
#             data = decode_avro(msg.value())
#             if not data:
#                 continue
            
#             truck_id = data.get('truck_id')
#             cargo = data.get('cargo', 'Unknown')
            
#             if not truck_id:
#                 continue
            
#             if is_duplicate(truck_id, cargo):
#                 continue
            
#             temp = data.get('temp', 0)
#             alert_msg = data.get('alert_message', 'Temperature anomaly')
#             cargo_value = state.trucks.get(truck_id, {}).get('cargo_value', 0)
            
#             add_log("FLINK", f"Alert: {truck_id} - {cargo} at {temp}C")
            
#             add_log("AI", f"Generating recommendation for {truck_id}...")
#             ai_start = time.time()
#             ai_rec = get_ai_recommendation(truck_id, cargo, temp, alert_msg, cargo_value)
#             ai_time = time.time() - ai_start
#             add_log("AI", f"Recommendation ready ({ai_time:.1f}s)")
            
#             alert = {
#                 'id': f"alert_{truck_id}_{int(time.time()*1000)}",
#                 'truck_id': truck_id,
#                 'cargo': cargo,
#                 'cargo_value': cargo_value,
#                 'temp': temp,
#                 'anomaly_type': 'TEMPERATURE_CRITICAL',
#                 'message': f"[Flink] {alert_msg}",
#                 'severity': 'critical',
#                 'timestamp': data.get('timestamp', datetime.now().isoformat()),
#                 'ai_recommendation': ai_rec
#             }
            
#             state.alerts.insert(0, alert)
#             if len(state.alerts) > 100:
#                 state.alerts = state.alerts[:100]
            
#             if truck_id in state.trucks:
#                 state.trucks[truck_id]['status'] = 'critical'
#                 await broadcast({'type': 'truck_update', 'data': state.trucks[truck_id]})
            
#             await broadcast({
#                 'type': 'alert',
#                 'data': alert,
#                 'stats': {'ai_calls': state.ai_calls, 'total_alerts': len(state.alerts)}
#             })
            
#             add_log("SERVER", f"Alert broadcast to {len(state.clients)} clients")
            
#         except Exception as e:
#             add_log("FLINK", f"Alert processing error: {str(e)[:40]}")
        
#         await asyncio.sleep(0.01)
    
#     consumer.close()


# @app.get("/")
# async def serve_dashboard():
#     return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     state.clients.add(websocket)
#     add_log("SERVER", f"Client connected. Total: {len(state.clients)}")
    
#     try:
#         await websocket.send_text(json.dumps({
#             'type': 'init',
#             'trucks': state.trucks,
#             'alerts': state.alerts[-30:],
#             'logs': state.logs[-50:],
#             'stats': {'ai_calls': state.ai_calls, 'total_alerts': len(state.alerts)},
#             'status': {'running': state.running, 'demo_mode': state.demo_mode}
#         }, default=str))
        
#         while True:
#             data = await websocket.receive_text()
#             msg = json.loads(data)
#             await handle_client_message(msg)
            
#     except WebSocketDisconnect:
#         state.clients.discard(websocket)
#         add_log("SERVER", f"Client disconnected. Total: {len(state.clients)}")
#     except Exception as e:
#         state.clients.discard(websocket)


# async def handle_client_message(msg):
#     cmd = msg.get('command')
    
#     if cmd == 'start':
#         if not state.running:
#             state.running = True
#             state.demo_mode = msg.get('demo', False)
#             state.cycle = 0
#             state.init_trucks()
#             mode = "AUTOMATIC" if state.demo_mode else "MANUAL"
#             add_log("SERVER", f"Starting simulation in {mode} mode")
            
#             state.gemini = init_gemini()
            
#             asyncio.create_task(simulator_loop())
#             asyncio.create_task(alerts_consumer_loop())
            
#             await broadcast({'type': 'status', 'running': True, 'demo_mode': state.demo_mode})
    
#     elif cmd == 'stop':
#         if state.running:
#             state.running = False
#             add_log("SERVER", "Stopping simulation")
#             await broadcast({'type': 'status', 'running': False, 'demo_mode': False})
    
#     elif cmd == 'trigger':
#         truck_num = msg.get('truck')
#         if truck_num and 1 <= truck_num <= 5:
#             truck_id = f"TRUCK_00{truck_num}"
#             if truck_id in state.truck_states:
#                 if not state.truck_states[truck_id]['is_critical']:
#                     state.truck_states[truck_id]['is_critical'] = True
#                     cfg = TRUCK_CONFIG[truck_id]
#                     state.truck_states[truck_id]['temp'] = cfg['temp_critical']
#                     add_log("SIMULATOR", f"[MANUAL] {truck_id} ({cfg['cargo']}) set to CRITICAL")
    
#     elif cmd == 'reset':
#         for truck_id in state.truck_states:
#             state.truck_states[truck_id]['is_critical'] = False
#             cfg = TRUCK_CONFIG[truck_id]
#             state.truck_states[truck_id]['temp'] = cfg['temp_optimal']
#         add_log("SIMULATOR", "All trucks reset to NORMAL")


# @app.on_event("startup")
# async def startup():
#     add_log("SERVER", "Cyber-Physical Guard server started")
#     add_log("SERVER", f"Static dir: {STATIC_DIR}")
#     if KAFKA_BOOTSTRAP:
#         add_log("SERVER", f"Kafka: {KAFKA_BOOTSTRAP[:30]}...")
#     else:
#         add_log("SERVER", "Kafka: Not configured - check .env file")


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))


"""
Cyber-Physical Guard - Unified Backend Server
"""

import os
import json
import asyncio
import time
import io
import random
from datetime import datetime
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer
import fastavro
import google.generativeai as genai
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

load_dotenv()

# Get the directory where app.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure static directory exists
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="Cyber-Physical Guard")

# Mount static files with absolute path
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

KAFKA_BOOTSTRAP = os.getenv('CONFLUENT_BOOTSTRAP_SERVERS')
KAFKA_KEY = os.getenv('CONFLUENT_API_KEY')
KAFKA_SECRET = os.getenv('CONFLUENT_API_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

TELEMETRY_TOPIC = 'truck_telemetry'
ALERTS_TOPIC = 'critical_alerts_json'

# Timeout settings (in seconds)
DEMO_TIMEOUT = 240  # 4 minutes - auto-stop demo
IDLE_TIMEOUT = 120  # 2 minutes - disconnect if no demo started

ALERT_SCHEMA = {
    "type": "record",
    "name": "critical_alerts_json",
    "fields": [
        {"name": "alert_level", "type": ["null", "string"], "default": None},
        {"name": "alert_message", "type": ["null", "string"], "default": None},
        {"name": "cargo", "type": ["null", "string"], "default": None},
        {"name": "temp", "type": ["null", "double"], "default": None},
        {"name": "timestamp", "type": ["null", "string"], "default": None},
        {"name": "truck_id", "type": ["null", "string"], "default": None}
    ]
}
PARSED_SCHEMA = fastavro.parse_schema(ALERT_SCHEMA)

TRUCK_CONFIG = {
    'TRUCK_001': {'cargo': 'Vaccines', 'cargo_value': 250000, 'temp_optimal': 5, 'temp_critical': 12, 'lat': 32.7767, 'lng': -96.7970},
    'TRUCK_002': {'cargo': 'Frozen Seafood', 'cargo_value': 85000, 'temp_optimal': -22, 'temp_critical': -15, 'lat': 29.7604, 'lng': -95.3698},
    'TRUCK_003': {'cargo': 'Electronics', 'cargo_value': 175000, 'temp_optimal': 22, 'temp_critical': 40, 'lat': 32.4487, 'lng': -99.7331},
    'TRUCK_004': {'cargo': 'Insulin', 'cargo_value': 320000, 'temp_optimal': 5, 'temp_critical': 12, 'lat': 30.2672, 'lng': -97.7431},
    'TRUCK_005': {'cargo': 'Fresh Produce', 'cargo_value': 45000, 'temp_optimal': 3, 'temp_critical': 8, 'lat': 29.4241, 'lng': -98.4936},
}

DEMO_SCHEDULE = {10: 'TRUCK_001', 25: 'TRUCK_004', 40: 'TRUCK_002', 55: 'TRUCK_005', 70: 'TRUCK_003'}


class SystemState:
    def __init__(self):
        self.clients = set()
        self.client_connect_times = {}  # Track when each client connected
        self.trucks = {}
        self.alerts = []
        self.logs = []
        self.processed_alerts = {}
        self.ai_calls = 0
        self.gemini = None
        self.producer = None
        self.running = False
        self.demo_mode = False
        self.cycle = 0
        self.truck_states = {}
        self.demo_start_time = None  # Track when demo started
        self.demo_timeout_task = None  # Task to auto-stop demo
        
    def init_trucks(self):
        for truck_id, cfg in TRUCK_CONFIG.items():
            self.truck_states[truck_id] = {
                'is_critical': False,
                'temp': cfg['temp_optimal'],
                'speed': random.uniform(65, 80),
                'fuel': random.uniform(75, 95),
                'lat': cfg['lat'],
                'lng': cfg['lng']
            }

state = SystemState()


def add_log(source, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"time": timestamp, "source": source, "message": message}
    state.logs.append(entry)
    if len(state.logs) > 200:
        state.logs = state.logs[-200:]
    # Safe broadcast - handle case when no event loop is running
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(broadcast({"type": "log", "data": entry}))
    except RuntimeError:
        pass  # No event loop running yet (startup)


def init_gemini():
    if not GEMINI_API_KEY:
        add_log("AI", "No GEMINI_API_KEY configured")
        return None
    
    genai.configure(api_key=GEMINI_API_KEY)
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            test = model.generate_content("OK")
            if test.text:
                add_log("AI", f"Initialized {model_name}")
                return model
        except Exception as e:
            add_log("AI", f"{model_name} unavailable: {str(e)[:40]}")
    
    return None


def get_ai_recommendation(truck_id, cargo, temp, alert_msg, cargo_value):
    if not state.gemini:
        return "AI service unavailable"
    
    prompt = f"""Fleet alert - respond in exactly 4 lines:

Truck: {truck_id} | Cargo: {cargo} (${cargo_value:,}) | Temp: {temp}C
Alert: {alert_msg}

Format:
SEVERITY: [Critical/High] - reason
ACTION: [specific action]
URGENCY: [timeframe]
NOTIFY: [who to contact]"""

    try:
        state.ai_calls += 1
        response = state.gemini.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI error: {str(e)[:50]}"


def decode_avro(data):
    if len(data) < 5:
        return None
    if data[0] != 0:
        try:
            return json.loads(data.decode('utf-8'))
        except:
            return None
    try:
        reader = io.BytesIO(data[5:])
        return fastavro.schemaless_reader(reader, PARSED_SCHEMA)
    except:
        return None


def is_duplicate(truck_id, cargo):
    key = f"{truck_id}_{cargo}"
    now = time.time()
    if key in state.processed_alerts:
        if now - state.processed_alerts[key] < 30:
            return True
    state.processed_alerts[key] = now
    return False


async def broadcast(message):
    if not state.clients:
        return
    
    msg_str = json.dumps(message, default=str)
    disconnected = set()
    
    for client in state.clients:
        try:
            await client.send_text(msg_str)
        except:
            disconnected.add(client)
    
    state.clients -= disconnected


async def demo_timeout_handler():
    """Auto-stop demo after DEMO_TIMEOUT seconds and close all connections"""
    await asyncio.sleep(DEMO_TIMEOUT)
    if state.running:
        state.running = False
        elapsed = int(time.time() - state.demo_start_time) if state.demo_start_time else 0
        add_log("SERVER", f"Demo auto-stopped after {elapsed}s (timeout: {DEMO_TIMEOUT}s)")
        
        # Send timeout message to all clients
        timeout_msg = json.dumps({
            'type': 'status', 
            'running': False, 
            'demo_mode': False,
            'reason': 'timeout',
            'message': f'Demo automatically stopped after {DEMO_TIMEOUT // 60} minutes. Click Restart to begin again.'
        })
        
        # Send message and close all connections
        for client in list(state.clients):
            try:
                await client.send_text(timeout_msg)
                await client.close()
            except:
                pass
        
        # Clear all clients
        state.clients.clear()
        state.client_connect_times.clear()
        state.demo_start_time = None
        add_log("SERVER", "All connections closed due to demo timeout")


async def check_idle_client(websocket):
    """Disconnect client if they don't start demo within IDLE_TIMEOUT"""
    await asyncio.sleep(IDLE_TIMEOUT)
    # Check if this client is still connected and demo hasn't started
    if websocket in state.clients and not state.running:
        add_log("SERVER", f"Idle client disconnected (no demo started in {IDLE_TIMEOUT}s)")
        try:
            await websocket.send_text(json.dumps({
                'type': 'disconnect',
                'reason': 'idle',
                'message': f'Connection closed due to {IDLE_TIMEOUT // 60} minutes of inactivity. Click Restart to reconnect.'
            }))
            await websocket.close()
        except:
            pass
        state.clients.discard(websocket)
        if websocket in state.client_connect_times:
            del state.client_connect_times[websocket]


def create_kafka_producer():
    if not KAFKA_BOOTSTRAP or not KAFKA_KEY or not KAFKA_SECRET:
        raise Exception("Kafka credentials not configured")
    config = {
        'bootstrap.servers': KAFKA_BOOTSTRAP,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': KAFKA_KEY,
        'sasl.password': KAFKA_SECRET,
    }
    return Producer(config)


def create_kafka_consumer(group_suffix):
    if not KAFKA_BOOTSTRAP or not KAFKA_KEY or not KAFKA_SECRET:
        raise Exception("Kafka credentials not configured")
    config = {
        'bootstrap.servers': KAFKA_BOOTSTRAP,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': KAFKA_KEY,
        'sasl.password': KAFKA_SECRET,
        'group.id': f'cpg-unified-{group_suffix}',
        'auto.offset.reset': 'latest'
    }
    return Consumer(config)


async def simulator_loop():
    add_log("SIMULATOR", "Starting fleet simulation")
    
    try:
        state.producer = create_kafka_producer()
        add_log("KAFKA", "Producer connected")
    except Exception as e:
        add_log("SIMULATOR", f"Kafka producer error: {str(e)[:50]}")
        return
    
    state.init_trucks()
    
    while state.running:
        state.cycle += 1
        
        if state.demo_mode and state.cycle in DEMO_SCHEDULE:
            truck_id = DEMO_SCHEDULE[state.cycle]
            if not state.truck_states[truck_id]['is_critical']:
                state.truck_states[truck_id]['is_critical'] = True
                cfg = TRUCK_CONFIG[truck_id]
                state.truck_states[truck_id]['temp'] = cfg['temp_critical']
                add_log("SIMULATOR", f"[AUTO] {truck_id} set to CRITICAL")
        
        if state.demo_mode and state.cycle > 80:
            state.cycle = 0
        
        for truck_id, ts in state.truck_states.items():
            cfg = TRUCK_CONFIG[truck_id]
            
            if ts['is_critical']:
                ts['temp'] = cfg['temp_critical'] + random.uniform(-0.3, 0.5)
            else:
                ts['temp'] = cfg['temp_optimal'] + random.uniform(-0.3, 0.3)
            
            ts['speed'] = random.uniform(60, 85)
            ts['fuel'] = max(50, ts['fuel'] - random.uniform(0.01, 0.03))
            ts['lat'] += random.uniform(-0.0005, 0.0005)
            ts['lng'] += random.uniform(-0.0005, 0.0005)
            
            status = 'critical' if ts['is_critical'] else 'normal'
            
            telemetry = {
                'truck_id': truck_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'cargo': cfg['cargo'],
                'cargo_value': cfg['cargo_value'],
                'temp': round(ts['temp'], 2),
                'speed': round(ts['speed'], 1),
                'speed_kmh': round(ts['speed'], 1),
                'fuel': round(ts['fuel'], 1),
                'fuel_level': round(ts['fuel'], 1),
                'lat': round(ts['lat'], 6),
                'lng': round(ts['lng'], 6),
                'status': status
            }
            
            state.trucks[truck_id] = telemetry
            
            try:
                state.producer.produce(
                    TELEMETRY_TOPIC,
                    key=truck_id,
                    value=json.dumps(telemetry)
                )
            except Exception as e:
                add_log("SIMULATOR", f"Kafka send error: {str(e)[:40]}")
            
            await broadcast({'type': 'truck_update', 'data': telemetry})
        
        try:
            state.producer.flush(timeout=1)
        except:
            pass
        
        if state.cycle % 5 == 0:
            critical_count = sum(1 for t in state.truck_states.values() if t['is_critical'])
            add_log("SIMULATOR", f"Cycle {state.cycle} | {len(state.trucks)} trucks | {critical_count} critical")
        
        await asyncio.sleep(2)
    
    add_log("SIMULATOR", "Simulation stopped")


async def alerts_consumer_loop():
    add_log("KAFKA", f"Subscribing to {ALERTS_TOPIC}")
    
    try:
        consumer = create_kafka_consumer("alerts")
        consumer.subscribe([ALERTS_TOPIC])
    except Exception as e:
        add_log("KAFKA", f"Consumer error: {str(e)[:50]}")
        return
    
    while state.running:
        msg = consumer.poll(0.1)
        if msg is None:
            await asyncio.sleep(0.05)
            continue
        if msg.error():
            continue
        
        try:
            data = decode_avro(msg.value())
            if not data:
                continue
            
            truck_id = data.get('truck_id')
            cargo = data.get('cargo', 'Unknown')
            
            if not truck_id:
                continue
            
            if is_duplicate(truck_id, cargo):
                continue
            
            temp = data.get('temp', 0)
            alert_msg = data.get('alert_message', 'Temperature anomaly')
            cargo_value = state.trucks.get(truck_id, {}).get('cargo_value', 0)
            
            add_log("FLINK", f"Alert: {truck_id} - {cargo} at {temp}C")
            
            add_log("AI", f"Generating recommendation for {truck_id}...")
            ai_start = time.time()
            ai_rec = get_ai_recommendation(truck_id, cargo, temp, alert_msg, cargo_value)
            ai_time = time.time() - ai_start
            add_log("AI", f"Recommendation ready ({ai_time:.1f}s)")
            
            alert = {
                'id': f"alert_{truck_id}_{int(time.time()*1000)}",
                'truck_id': truck_id,
                'cargo': cargo,
                'cargo_value': cargo_value,
                'temp': temp,
                'anomaly_type': 'TEMPERATURE_CRITICAL',
                'message': f"[Flink] {alert_msg}",
                'severity': 'critical',
                'timestamp': data.get('timestamp', datetime.now().isoformat()),
                'ai_recommendation': ai_rec
            }
            
            state.alerts.insert(0, alert)
            if len(state.alerts) > 100:
                state.alerts = state.alerts[:100]
            
            if truck_id in state.trucks:
                state.trucks[truck_id]['status'] = 'critical'
                await broadcast({'type': 'truck_update', 'data': state.trucks[truck_id]})
            
            await broadcast({
                'type': 'alert',
                'data': alert,
                'stats': {'ai_calls': state.ai_calls, 'total_alerts': len(state.alerts)}
            })
            
            add_log("SERVER", f"Alert broadcast to {len(state.clients)} clients")
            
        except Exception as e:
            add_log("FLINK", f"Alert processing error: {str(e)[:40]}")
        
        await asyncio.sleep(0.01)
    
    consumer.close()


@app.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.clients.add(websocket)
    state.client_connect_times[websocket] = time.time()
    add_log("SERVER", f"Client connected. Total: {len(state.clients)}")
    
    # Start idle timeout check (will disconnect if no demo started)
    idle_task = asyncio.create_task(check_idle_client(websocket))
    
    try:
        # Calculate remaining demo time if running
        remaining_time = None
        if state.running and state.demo_start_time:
            elapsed = time.time() - state.demo_start_time
            remaining_time = max(0, DEMO_TIMEOUT - elapsed)
        
        await websocket.send_text(json.dumps({
            'type': 'init',
            'trucks': state.trucks,
            'alerts': state.alerts[-30:],
            'logs': state.logs[-50:],
            'stats': {'ai_calls': state.ai_calls, 'total_alerts': len(state.alerts)},
            'status': {'running': state.running, 'demo_mode': state.demo_mode},
            'timeouts': {
                'demo_timeout': DEMO_TIMEOUT,
                'idle_timeout': IDLE_TIMEOUT,
                'remaining_time': remaining_time
            }
        }, default=str))
        
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            # Cancel idle timeout if client sends any command
            if not idle_task.done():
                idle_task.cancel()
            
            await handle_client_message(msg, websocket)
            
    except WebSocketDisconnect:
        state.clients.discard(websocket)
        if websocket in state.client_connect_times:
            del state.client_connect_times[websocket]
        if not idle_task.done():
            idle_task.cancel()
        add_log("SERVER", f"Client disconnected. Total: {len(state.clients)}")
    except Exception as e:
        state.clients.discard(websocket)
        if websocket in state.client_connect_times:
            del state.client_connect_times[websocket]
        if not idle_task.done():
            idle_task.cancel()


async def handle_client_message(msg, websocket=None):
    cmd = msg.get('command')
    
    if cmd == 'start':
        if not state.running:
            state.running = True
            state.demo_mode = msg.get('demo', False)
            state.cycle = 0
            state.demo_start_time = time.time()
            state.init_trucks()
            mode = "AUTOMATIC" if state.demo_mode else "MANUAL"
            add_log("SERVER", f"Starting simulation in {mode} mode (auto-stop in {DEMO_TIMEOUT}s)")
            
            state.gemini = init_gemini()
            
            # Start demo timeout
            if state.demo_timeout_task and not state.demo_timeout_task.done():
                state.demo_timeout_task.cancel()
            state.demo_timeout_task = asyncio.create_task(demo_timeout_handler())
            
            asyncio.create_task(simulator_loop())
            asyncio.create_task(alerts_consumer_loop())
            
            await broadcast({
                'type': 'status', 
                'running': True, 
                'demo_mode': state.demo_mode,
                'demo_timeout': DEMO_TIMEOUT,
                'started_at': state.demo_start_time
            })
    
    elif cmd == 'stop':
        if state.running:
            state.running = False
            state.demo_start_time = None
            
            # Cancel demo timeout
            if state.demo_timeout_task and not state.demo_timeout_task.done():
                state.demo_timeout_task.cancel()
                state.demo_timeout_task = None
            
            add_log("SERVER", "Stopping simulation (manual)")
            await broadcast({'type': 'status', 'running': False, 'demo_mode': False})
    
    elif cmd == 'trigger':
        truck_num = msg.get('truck')
        if truck_num and 1 <= truck_num <= 5:
            truck_id = f"TRUCK_00{truck_num}"
            if truck_id in state.truck_states:
                if not state.truck_states[truck_id]['is_critical']:
                    state.truck_states[truck_id]['is_critical'] = True
                    cfg = TRUCK_CONFIG[truck_id]
                    state.truck_states[truck_id]['temp'] = cfg['temp_critical']
                    add_log("SIMULATOR", f"[MANUAL] {truck_id} ({cfg['cargo']}) set to CRITICAL")
    
    elif cmd == 'reset':
        for truck_id in state.truck_states:
            state.truck_states[truck_id]['is_critical'] = False
            cfg = TRUCK_CONFIG[truck_id]
            state.truck_states[truck_id]['temp'] = cfg['temp_optimal']
        add_log("SIMULATOR", "All trucks reset to NORMAL")


@app.on_event("startup")
async def startup():
    add_log("SERVER", "Cyber-Physical Guard server started")
    add_log("SERVER", f"Static dir: {STATIC_DIR}")
    if KAFKA_BOOTSTRAP:
        add_log("SERVER", f"Kafka: {KAFKA_BOOTSTRAP[:30]}...")
    else:
        add_log("SERVER", "Kafka: Not configured - check .env file")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))


