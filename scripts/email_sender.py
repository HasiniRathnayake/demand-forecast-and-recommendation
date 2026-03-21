# scripts/email_sender.py
import smtplib
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from scripts.db_connection import DatabaseConnection

class EmailSender:
    def __init__(self):
        self.db         = DatabaseConnection()
        self.smtp_host  = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.smtp_port  = int(os.getenv("EMAIL_PORT", 587))
        self.email_user = os.getenv("EMAIL_USER")
        self.email_pass = os.getenv("EMAIL_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")

    def build_email_html(self, offer):
        """Build a nice HTML email for the customer"""
        name         = offer['customer_name']
        offer_text   = offer['offer_text']
        discount_pct = offer['discount_pct']
        friendly_segments = {
            'VIP Customer':     'VIP Member',
            'High Value':       'Valued Member',
            'Regular Customer': 'Loyal Member',
            'At Risk':          'Valued Member',
            'Occasional':       'Special Member',
            'New Customer':     'New Member',
            'Churned':          'Valued Member',
        }
        segment = friendly_segments.get(offer['segment'], 'Loyalty Member')
        recommended  = offer['recommended']

        # Build product cards
        product_rows = ""
        for p in recommended:
            saving = round(p['unit_price'] - p['offer_price'], 2)
            saving_html = f"<span style='color:#e74c3c;'>Save Rs.{saving:.2f}</span>" if saving > 0 else ""
            product_rows += f"""
            <tr>
                <td style="padding:10px;border-bottom:1px solid #eee;">
                    <strong>{p['product_name']}</strong><br>
                    <small style="color:#888;">{p['category']}</small>
                </td>
                <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">
                    <span style="text-decoration:line-through;color:#aaa;">Rs.{p['unit_price']:.2f}</span><br>
                    <strong style="color:#27ae60;">Rs.{p['offer_price']:.2f}</strong><br>
                    <small>{saving_html}</small>
                </td>
            </tr>
            """

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
            <div style="max-width:600px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);">

                <!-- Header -->
                <div style="background:linear-gradient(135deg,#2ecc71,#27ae60);padding:30px;text-align:center;">
                    <h1 style="color:#fff;margin:0;font-size:28px;">🛒 Sunrise Super</h1>
                    <p style="color:#d5f5e3;margin:8px 0 0;">Smart Loyalty Rewards</p>
                </div>

                <!-- Greeting -->
                <div style="padding:30px;">
                    <h2 style="color:#2c3e50;">Hi {name}! 👋</h2>
                    <p style="color:#555;font-size:16px;">
                        As a valued <strong>{segment}</strong> member, we have an exclusive offer just for you:
                    </p>

                    <!-- Offer Badge -->
                    <div style="background:#fff3cd;border:2px dashed #f39c12;border-radius:10px;padding:20px;text-align:center;margin:20px 0;">
                        <h2 style="color:#e67e22;margin:0;font-size:32px;">🎉 {offer_text}</h2>
                        <p style="color:#888;margin:8px 0 0;">Use at checkout — valid this week only</p>
                    </div>

                    <!-- Recommended Products -->
                    <h3 style="color:#2c3e50;">🎯 Recommended Just For You</h3>
                    <table style="width:100%;border-collapse:collapse;">
                        <tr style="background:#f8f9fa;">
                            <th style="padding:10px;text-align:left;color:#888;">Product</th>
                            <th style="padding:10px;text-align:center;color:#888;">Price</th>
                        </tr>
                        {product_rows}
                    </table>

                    <!-- Footer message -->
                    <p style="color:#888;font-size:13px;margin-top:30px;text-align:center;">
                        Thank you for shopping with us!<br>
                        <strong>Sunrise Super — Fresh Every Day</strong>
                    </p>
                </div>

                <!-- Footer -->
                <div style="background:#f8f9fa;padding:15px;text-align:center;">
                    <p style="color:#aaa;font-size:12px;margin:0;">
                        You received this because you are a Sunrise Super loyalty member.<br>
                        To unsubscribe, visit our store or contact us.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_email(self, to_email, subject, html_content):
        """Send a single email"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = self.email_from
            msg['To']      = to_email
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_pass)
                server.sendmail(self.email_from, to_email, msg.as_string())
            return True, "Sent"
        except Exception as e:
            return False, str(e)

    def log_email(self, customer_id, email_type, subject, html_content, status, segment=None):
        """Save email record to email_log table with simulated engagement"""
        import random
        delivery_status = 'sent' if status else 'failed'

        # Simulated open/click rates by segment (industry realistic benchmarks)
        open_rates = {
            'VIP Customer':     0.75,
            'High Value':       0.65,
            'Regular Customer': 0.55,
            'At Risk':          0.40,
            'Occasional':       0.35,
            'New Customer':     0.50,
            'Churned':          0.25,
        }
        click_rates = {
            'VIP Customer':     0.45,
            'High Value':       0.38,
            'Regular Customer': 0.30,
            'At Risk':          0.20,
            'Occasional':       0.18,
            'New Customer':     0.25,
            'Churned':          0.10,
        }

        open_rate  = open_rates.get(segment, 0.40)
        click_rate = click_rates.get(segment, 0.20)

        opened  = status and random.random() < open_rate
        clicked = opened and random.random() < click_rate

        self.db.execute_query("""
            INSERT INTO email_log
            (customer_id, email_type, subject, email_content,
             sent_date, delivery_status, opened, clicked)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
        """, [customer_id, email_type, subject, html_content,
              delivery_status, opened, clicked])

    def send_promotional_emails(self, offers, test_mode=False):
        sent    = 0
        skipped = 0
        failed  = 0
        results = []

        # Open ONE connection for all emails instead of one per email
        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_pass)
        except Exception as e:
            return {
                'sent': 0, 'skipped': 0, 'failed': len(offers),
                'results': [{'name': 'All', 'email': '-',
                             'status': 'failed', 'reason': str(e)}]
            }

        for offer in offers:
            if not offer.get('email_enabled') or not offer.get('promo_allowed'):
                skipped += 1
                results.append({
                    'name':   offer['customer_name'],
                    'email':  offer['email'],
                    'status': 'skipped',
                    'reason': 'Email notifications disabled'
                })
                continue

            subject      = f"🎉 {offer['offer_text']} — Sunrise Super"
            html_content = self.build_email_html(offer)
            target_email = self.email_user if test_mode else offer['email']

            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From']    = self.email_from
                msg['To']      = target_email
                msg.attach(MIMEText(html_content, 'html'))
                server.sendmail(self.email_from, target_email, msg.as_string())

                self.log_email(
                    offer['customer_id'], 'promotional',
                    subject, html_content, True,
                    segment=offer.get('segment')
                )
                sent += 1
                results.append({
                    'name':   offer['customer_name'],
                    'email':  offer['email'],
                    'status': 'sent',
                    'reason': offer['offer_text']
                })
            except Exception as e:
                self.log_email(
                    offer['customer_id'], 'promotional',
                    subject, html_content, False,
                    segment=offer.get('segment')
                )
                failed += 1
                results.append({
                    'name':   offer['customer_name'],
                    'email':  offer['email'],
                    'status': 'failed',
                    'reason': str(e)
                })

        server.quit()

        return {
            'sent':    sent,
            'skipped': skipped,
            'failed':  failed,
            'results': results
        }


if __name__ == "__main__":
    from scripts.segmentation import CustomerSegmentation
    from scripts.offers_engine import OffersEngine

    print("Running segmentation...")
    seg       = CustomerSegmentation()
    customers = seg.run()

    print("Generating offers...")
    engine = OffersEngine()
    offers = engine.generate_all_offers(customers)

    print("Sending test email to your address...")
    sender  = EmailSender()
    # test_mode=True sends to YOUR email, not customer emails
    summary = sender.send_promotional_emails(offers, test_mode=True)

    print(f"\n✅ Sent:    {summary['sent']}")
    print(f"⏭️  Skipped: {summary['skipped']}")
    print(f"❌ Failed:  {summary['failed']}")
    print("\nDetails:")
    for r in summary['results']:
        icon = "✅" if r['status'] == 'sent' else "⏭️" if r['status'] == 'skipped' else "❌"
        print(f"  {icon} {r['name']:15} | {r['status']:8} | {r['reason']}")