# scripts/email_sender.py
import smtplib
import os
import sys
import html
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
        promo_start  = offer.get('promo_start')
        promo_end    = offer.get('promo_end')
        taste_pref   = (offer.get('taste_preference') or '').strip()
        campaign_message = (offer.get('campaign_message') or '').strip()
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
        intro_message = campaign_message or (
            f"As a valued {segment} member, we have an exclusive offer just for you:"
        )
        intro_message_html = html.escape(intro_message).replace('\n', '<br>')
        taste_pref_html = (
            f"<p style=\"margin:0 0 14px;color:#16a085;font-size:13px;\">"
            f"Taste Profile: <strong>{html.escape(taste_pref)}</strong></p>"
            if taste_pref else ""
        )
        validity_line = (
            f"Use at checkout — valid from {promo_start} to {promo_end}"
            if promo_start and promo_end else
            "Use at checkout — valid this week only"
        )

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

        html_body = f"""
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
                        {intro_message_html}
                    </p>
                    {taste_pref_html}

                    <!-- Offer Badge -->
                    <div style="background:#fff3cd;border:2px dashed #f39c12;border-radius:10px;padding:20px;text-align:center;margin:20px 0;">
                        <h2 style="color:#e67e22;margin:0;font-size:32px;">🎉 {offer_text}</h2>
                        <p style="color:#888;margin:8px 0 0;">{validity_line}</p>
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
        return html_body

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

    def build_supplier_po_html(self, po_data):
        """Build HTML email for purchase order sent to supplier"""
        supplier_name = po_data.get('supplier_name', 'Valued Partner')
        po_id = po_data.get('po_id', 'PO-UNKNOWN')
        product_name = po_data.get('product_name', 'Product')
        product_code = po_data.get('product_code', 'SKU-UNKNOWN')
        quantity = po_data.get('quantity', 0)
        order_date = po_data.get('order_date', datetime.now().strftime('%Y-%m-%d'))
        expected_delivery = po_data.get('expected_delivery_date', 'To be confirmed')
        supplier_note = (po_data.get('notes') or '').strip()
        note_html = (
            f"""
                    <h3 style="color:#2c3e50;margin-top:25px;">🗒️ Note from Admin</h3>
                    <div style="background:#fff7ed;border-left:4px solid #fb923c;border-radius:6px;padding:12px 14px;color:#7c2d12;">
                        {supplier_note}
                    </div>
            """
            if supplier_note else ""
        )
        store_name = "Sunrise Super"
        
        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
            <div style="max-width:700px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);">

                <!-- Header -->
                <div style="background:linear-gradient(135deg,#1e3c72,#2a5298);padding:30px;text-align:center;color:#fff;">
                    <h1 style="margin:0;font-size:28px;">📦 Purchase Order</h1>
                    <p style="margin:8px 0 0;font-size:14px;opacity:0.9;">New Order Received</p>
                </div>

                <!-- Content -->
                <div style="padding:30px;">
                    <p style="color:#333;font-size:16px;">Dear <strong>{supplier_name}</strong>,</p>
                    <p style="color:#555;">We have a new purchase order for you. Please review the details below and confirm receipt.</p>

                    <!-- PO Details Box -->
                    <div style="background:#f8f9fa;border-left:4px solid #2a5298;padding:20px;margin:20px 0;border-radius:6px;">
                        <table style="width:100%;margin:0;">
                            <tr>
                                <td style="padding:8px 0;"><strong>PO Number:</strong></td>
                                <td style="padding:8px 0;text-align:right;"><code style="background:#e8eef7;padding:4px 8px;border-radius:4px;font-weight:bold;">{po_id}</code></td>
                            </tr>
                            <tr>
                                <td style="padding:8px 0;"><strong>Order Date:</strong></td>
                                <td style="padding:8px 0;text-align:right;">{order_date}</td>
                            </tr>
                            <tr>
                                <td style="padding:8px 0;"><strong>Expected Delivery:</strong></td>
                                <td style="padding:8px 0;text-align:right;color:#27ae60;font-weight:bold;">{expected_delivery}</td>
                            </tr>
                        </table>
                    </div>

                    <!-- Product Details -->
                    <h3 style="color:#2c3e50;margin-top:25px;margin-bottom:10px;">📋 Order Items</h3>
                    <table style="width:100%;border-collapse:collapse;border:1px solid #ddd;">
                        <tr style="background:#2a5298;color:#fff;">
                            <th style="padding:12px;text-align:left;">Product Code</th>
                            <th style="padding:12px;text-align:left;">Product Name</th>
                            <th style="padding:12px;text-align:center;">Quantity</th>
                        </tr>
                        <tr style="border-bottom:1px solid #ddd;">
                            <td style="padding:12px;"><code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;">{product_code}</code></td>
                            <td style="padding:12px;">{product_name}</td>
                            <td style="padding:12px;text-align:center;font-weight:bold;font-size:18px;color:#27ae60;">{quantity} units</td>
                        </tr>
                    </table>

                    <!-- Instructions -->
                    <h3 style="color:#2c3e50;margin-top:25px;">📝 Next Steps</h3>
                    <ol style="color:#555;line-height:1.8;">
                        <li>Please confirm receipt of this purchase order</li>
                        <li>Prepare the items for shipment</li>
                        <li>Ensure delivery by <strong>{expected_delivery}</strong></li>
                        <li>Include PO number <code>{po_id}</code> on all shipping documents</li>
                    </ol>

                    {note_html}

                    <!-- Contact -->
                    <div style="background:#e8f4f8;border-radius:6px;padding:15px;margin-top:25px;border-left:4px solid #3498db;">
                        <p style="color:#2c3e50;margin:0;"><strong>Questions?</strong></p>
                        <p style="color:#555;margin:5px 0 0;font-size:14px;">Contact us for any clarifications regarding this order.</p>
                    </div>

                </div>

                <!-- Footer -->
                <div style="background:#f8f9fa;padding:20px;text-align:center;border-top:1px solid #eee;">
                    <p style="color:#888;font-size:12px;margin:0;">
                        <strong>{store_name}</strong><br>
                        Automated Purchase Order System<br>
                        <em>This is an automated message. Please do not reply to this email.</em>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_supplier_po_email(self, supplier_email, po_data):
        """Send purchase order email to supplier"""
        try:
            subject = f"Purchase Order {po_data.get('po_id', 'PO-UNKNOWN')} - {po_data.get('store_name', 'Sunrise Super')}"
            html_content = self.build_supplier_po_html(po_data)
            success, msg = self.send_email(supplier_email, subject, html_content)
            return success, msg
        except Exception as e:
            return False, str(e)

    def queue_scheduled_emails(self, offers, send_date, test_mode=False):
        """Queue emails for future sending in email_log with status='scheduled'."""
        queued = 0
        skipped = 0
        failed = 0
        results = []

        for offer in offers:
            if not offer.get('email_enabled') or not offer.get('promo_allowed'):
                skipped += 1
                results.append({
                    'name': offer['customer_name'],
                    'email': offer['email'],
                    'status': 'skipped',
                    'reason': 'Email notifications disabled'
                })
                continue

            try:
                subject = f"🎉 {offer['offer_text']} — Sunrise Super"
                html_content = self.build_email_html(offer)
                email_type = 'promotional_scheduled_test' if test_mode else 'promotional_scheduled'

                ok = self.db.execute_query(
                    """
                    INSERT INTO email_log
                    (customer_id, email_type, subject, email_content,
                     sent_date, delivery_status, opened, clicked)
                    VALUES (%s, %s, %s, %s, %s, 'scheduled', FALSE, FALSE)
                    """,
                    [offer['customer_id'], email_type, subject, html_content, send_date]
                )

                if ok:
                    queued += 1
                    results.append({
                        'name': offer['customer_name'],
                        'email': offer['email'],
                        'status': 'scheduled',
                        'reason': str(send_date)
                    })
                else:
                    failed += 1
                    results.append({
                        'name': offer['customer_name'],
                        'email': offer['email'],
                        'status': 'failed',
                        'reason': 'Failed to queue in email_log'
                    })
            except Exception as e:
                failed += 1
                results.append({
                    'name': offer.get('customer_name', '-'),
                    'email': offer.get('email', '-'),
                    'status': 'failed',
                    'reason': str(e)
                })

        return {
            'queued': queued,
            'skipped': skipped,
            'failed': failed,
            'results': results,
        }

    def process_due_scheduled_emails(self):
        """Send all scheduled emails due today or earlier."""
        due_rows = self.db.fetch_all(
            """
            SELECT el.email_log_id, el.customer_id, el.subject, el.email_content,
                   el.email_type, c.first_name, c.email
            FROM email_log el
            JOIN customers c ON el.customer_id = c.customer_id
            WHERE el.delivery_status = 'scheduled'
              AND DATE(el.sent_date) <= CURRENT_DATE
            ORDER BY el.sent_date, el.email_log_id
            """
        )

        if not due_rows:
            return {'sent': 0, 'failed': 0, 'total_due': 0, 'results': []}

        results = []
        sent = 0
        failed = 0

        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_pass)
        except Exception as e:
            return {
                'sent': 0,
                'failed': len(due_rows),
                'total_due': len(due_rows),
                'results': [{'name': 'All', 'email': '-', 'status': 'failed', 'reason': str(e)}],
            }

        for row in due_rows:
            log_id, _customer_id, subject, html_content, email_type, first_name, customer_email = row
            target_email = self.email_user if email_type == 'promotional_scheduled_test' else customer_email

            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = self.email_from
                msg['To'] = target_email
                msg.attach(MIMEText(html_content, 'html'))

                server.sendmail(self.email_from, target_email, msg.as_string())

                self.db.execute_query(
                    """
                    UPDATE email_log
                    SET delivery_status = 'sent', sent_date = CURRENT_TIMESTAMP
                    WHERE email_log_id = %s
                    """,
                    [log_id]
                )
                sent += 1
                results.append({
                    'name': first_name or 'Customer',
                    'email': customer_email,
                    'status': 'sent',
                    'reason': 'Scheduled email sent'
                })
            except Exception as e:
                self.db.execute_query(
                    """
                    UPDATE email_log
                    SET delivery_status = 'failed'
                    WHERE email_log_id = %s
                    """,
                    [log_id]
                )
                failed += 1
                results.append({
                    'name': first_name or 'Customer',
                    'email': customer_email,
                    'status': 'failed',
                    'reason': str(e)
                })

        server.quit()

        return {
            'sent': sent,
            'failed': failed,
            'total_due': len(due_rows),
            'results': results,
        }

    def log_email(self, customer_id, email_type, subject, html_content, status, segment=None):
        """Save email record to email_log table with simulated engagement"""
        import random
        delivery_status = 'sent' if status else 'failed'

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
        opened     = status and random.random() < open_rate
        clicked    = opened and random.random() < click_rate

        print(f"DEBUG: Logging email for {customer_id}, status={delivery_status}")
        result = self.db.execute_query("""
            INSERT INTO email_log
            (customer_id, email_type, subject, email_content,
             sent_date, delivery_status, opened, clicked)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
        """, [customer_id, email_type, subject, html_content,
              delivery_status, opened, clicked])
        print(f"DEBUG: Log result = {result}")

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