"""shopvotritemobil.com Contact form -> SNS topic votrite-shop-contact (emailed to Votrite Mobil).
Every message is also written to CloudWatch Logs, so nothing is lost if an email bounces."""
import json, os, re, boto3

sns = boto3.client("sns")
TOPIC = os.environ["TOPIC_ARN"]
ORIGINS = {"https://shopvotritemobil.com", "https://www.shopvotritemobil.com"}
FIELDS = [("name", "Name", 100), ("business", "Business", 150), ("email", "Email", 150),
          ("phone", "Phone", 40), ("interest", "Interested in", 100), ("message", "Message", 4000)]


def reply(code, body):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def handler(event, context):
    hdr = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return reply(405, {"ok": False})
    if hdr.get("origin") not in ORIGINS:
        return reply(403, {"ok": False, "error": "origin"})
    try:
        raw = event.get("body") or ""
        if event.get("isBase64Encoded"):
            import base64; raw = base64.b64decode(raw).decode()
        data = json.loads(raw)
    except Exception:
        return reply(400, {"ok": False, "error": "bad request"})
    if data.get("website"):          # honeypot: people never fill it, bots do
        return reply(200, {"ok": True})
    vals = {k: str(data.get(k, "")).strip()[:lim] for k, _, lim in FIELDS}
    if not vals["name"] or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", vals["email"]) or not vals["message"]:
        return reply(400, {"ok": False, "error": "Please fill in your name, a valid email and a message."})
    body = "New message from the Contact form on shopvotritemobil.com\n\n" + \
           "\n".join(f"{label}: {vals[k] or '-'}" for k, label, _ in FIELDS[:5]) + \
           f"\n\nMessage:\n{vals['message']}\n\nTo answer, write to {vals['email']}."
    subject = re.sub(r"[^\x20-\x7E]", "", f"Votrite Mobil Shop inquiry - {vals['business'] or vals['name']}")[:99]
    print(json.dumps({"contact": vals, "ip": event.get("requestContext", {}).get("http", {}).get("sourceIp")}))
    sns.publish(TopicArn=TOPIC, Subject=subject, Message=body)
    return reply(200, {"ok": True})
