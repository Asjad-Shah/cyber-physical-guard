# Cyber-Physical Guard

A real-time fleet monitoring system that detects temperature anomalies in cargo trucks and generates AI-powered recommendations for fleet operators.

Built for the Confluent Challenge at Google Cloud Hackathon 2024.

---

## The Problem

Cold chain logistics is broken. Temperature-sensitive cargo worth billions of dollars is lost every year because monitoring systems are too slow. By the time someone notices a problem, the damage is already done.

### The Numbers

The cold chain industry loses approximately **$35 billion annually** due to temperature failures in pharmaceutical and food logistics. Around **30% of vaccines** fail to reach patients because of temperature excursions during transport.

### Real Companies, Real Losses

**Pfizer & Moderna** - During the COVID-19 pandemic, millions of vaccine doses were wasted due to temperature control failures. These vaccines required strict cold storage between -70°C and -20°C, and even brief excursions meant entire shipments had to be discarded.
[Source: NBC News](https://www.nbcnews.com/news/us-news/covid-vaccine-doses-wasted-rcna31399)

**Johnson & Johnson** - In 2021, quality control issues at a manufacturing facility led to the destruction of 15 million COVID-19 vaccine doses. Temperature management was a critical factor in the production and storage failures.
[Source: CBS News](https://www.cbsnews.com/news/quality-control-issues-force-johnson-johnson-to-scrap-doses-of-covid-19-vaccine/)

**Walmart** - Operating over 10,000 refrigerated trucks, Walmart loses billions annually to produce spoilage. The company has invested heavily in AI solutions to combat this problem, showing just how significant the issue is for even the largest retailers.
[Source: Forbes](https://www.forbes.com/sites/edgarsten/2020/11/04/former-walmart-execs-company-uses-ai-to-battle-billions-in-spoiled-produce/)

**Novo Nordisk** - As one of the world's largest insulin manufacturers, Novo Nordisk faces constant cold chain challenges. Insulin must be stored between 2°C and 8°C - anything outside this range compromises the medication that millions of diabetics depend on daily.
[Source: Novo Nordisk Medical](https://www.novonordiskmedical.com/product-information/temperature-questions-and-answers.html)

**Maersk** - The world's largest shipping company moves thousands of refrigerated containers globally. A single container of frozen seafood that loses temperature control can mean over $100,000 in losses, not counting the environmental waste and supply chain disruption.
[Source: FreightAmigo](https://www.freightamigo.com/en/blog/logistics/challenges-in-cold-chain-logistics-for-frozen-foods/)

### Why Current Solutions Fail

Most cold chain monitoring today works like this: sensors log temperature data, someone reviews it hours or days later, and by then the cargo is already spoiled. There's no real-time detection, no immediate alerts, and definitely no intelligent recommendations on what to do when something goes wrong.

The industry needs a system that catches temperature anomalies the moment they happen and tells operators exactly what to do about it.

---

## The Solution

Cyber-Physical Guard solves this by combining real-time stream processing with AI-powered decision support.

This system monitors 5 trucks carrying different temperature-sensitive cargo:
- **Vaccines** (2°C to 8°C)
- **Insulin** (2°C to 8°C)
- **Frozen Seafood** (below -18°C)
- **Electronics** (10°C to 35°C)
- **Fresh Produce** (below 5°C)

When temperatures go out of range, Flink SQL catches it within seconds and triggers an alert. The alert flows to Google Gemini AI, which generates specific recommendations - not just "temperature is high" but actionable steps like which facility to reroute to, what backup measures to activate, and who to notify.

The dashboard shows everything in real-time on a map. Trucks turn red when they're in trouble, and clicking on them reveals the full AI analysis.

---

## Architecture

![System Architecture](docs/images/architecture.png)

The data flows like this:

- Fleet simulator sends truck telemetry to Kafka every 2 seconds
- Flink SQL watches the stream and filters for temperature violations
- When something's wrong, it pushes to a separate alerts topic
- My FastAPI server picks up those alerts, hits Gemini for analysis, and broadcasts to the dashboard via WebSocket
- BigQuery stores everything for historical analysis

---

## Screenshots

![Upload Interface](docs/images/Screenshot%202025-12-28%20235429.png)
![Validation Progress](docs/images/Screenshot%202025-12-29%20131824.png)
![Compliance Results](docs/images/Screenshot%202025-12-29%20132054.png)
![Detailed Feedback](docs/images/Screenshot%202025-12-29%20132236.png)
![Report View](docs/images/Screenshot%202025-12-29%20142702.png)
![Actions Panel](docs/images/Screenshot%202025-12-29%20143430.png)
![Download Dialog](docs/images/Screenshot%202025-12-29%20145052.png)

---

## Tech Stack

- Confluent Cloud (Kafka + Flink SQL + Schema Registry)
- Google Cloud (BigQuery + Gemini 2.0 Flash)
- Python with FastAPI for the backend
- Vanilla JS with Leaflet.js for the map

---

## Running It Locally

Clone the repo and install dependencies:

```bash
git clone https://github.com/Asjad-Shah/cyber-physical-guard.git
cd cyber-physical-guard
pip install -r requirements.txt
```

Copy the env template and add your credentials:

```bash
cp .env.example .env
```

You will need:
- Confluent Cloud account (use promo code CONFLUENTDEV1 for free credits)
- Google Cloud project with Gemini API enabled

Then just run:

```bash
python app.py
```

Open http://localhost:8000 and click "Start Demo". You can run it in automatic mode where alerts trigger themselves, or manual mode where you pick which truck goes critical.

---

## Confluent Setup

Create two topics in Confluent Cloud:
- `truck_telemetry` (JSON, 6 partitions)
- `critical_alerts_json` (AVRO, 6 partitions)

The Flink SQL query that does the anomaly detection:

```sql
INSERT INTO `critical_alerts_json`
SELECT 
    'CRITICAL' AS alert_level,
    CASE 
        WHEN cargo = 'Vaccines' AND temp > 8 THEN 'Vaccine temperature exceeded 8C'
        WHEN cargo = 'Vaccines' AND temp < 2 THEN 'Vaccine temperature too low'
        WHEN cargo = 'Frozen Seafood' AND temp > -18 THEN 'Frozen seafood thawing'
        WHEN cargo = 'Insulin' AND temp > 8 THEN 'Insulin temperature critical'
        WHEN cargo = 'Insulin' AND temp < 2 THEN 'Insulin temperature too low'
        WHEN cargo = 'Electronics' AND temp > 35 THEN 'Electronics overheating'
        WHEN cargo = 'Electronics' AND temp < 10 THEN 'Electronics too cold'
        WHEN cargo = 'Fresh Produce' AND temp > 5 THEN 'Fresh produce temperature high'
        ELSE 'Temperature anomaly detected'
    END AS alert_message,
    cargo,
    temp,
    `timestamp`,
    truck_id
FROM `truck_telemetry`
WHERE 
    (cargo = 'Vaccines' AND (temp > 8 OR temp < 2))
    OR (cargo = 'Frozen Seafood' AND temp > -18)
    OR (cargo = 'Insulin' AND (temp > 8 OR temp < 2))
    OR (cargo = 'Electronics' AND (temp > 35 OR temp < 10))
    OR (cargo = 'Fresh Produce' AND temp > 5);
```

---

## Project Structure

```
├── app.py              # FastAPI server, Kafka consumers, simulator
├── requirements.txt
├── render.yaml         # Deployment config
├── static/
│   ├── index.html      # Dashboard
│   └── diagram.jpeg    # Architecture diagram
└── docs/images/        # Screenshots for readme
```

---

## What I Learned

Flink SQL is surprisingly powerful. I thought I'd need to write a bunch of Python code to detect anomalies, but a simple WHERE clause does the job. The tricky part was getting the AVRO serialization right between Flink and my Python consumer.

WebSocket timeouts matter in production. I added automatic session limits (4 min demo, 2 min idle disconnect) after realizing an open demo could run forever and eat up resources.

Gemini 2.0 Flash is fast enough for real-time use. The AI recommendations come back in under 2 seconds, which feels instant in the context of an alert workflow.

---

## Demo Modes

**Automatic** - Sit back and watch. Different trucks will go critical every 20-30 seconds, triggering the full alert pipeline.

**Manual** - Click the truck buttons (1-5) to trigger specific scenarios. Good for showing off particular cargo types.

---

## License

MIT

---

Syed Asjad Sohail
asjadshah60@gmail.com
www.linkedin.com/in/syed-asjad-sohail-b388271a0