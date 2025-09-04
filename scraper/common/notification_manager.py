import requests
import json
import datetime # Added import for datetime

class NotificationManager:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.ignore_identical_values = False
        self.last_notification_time = None
        self.notification_queue = []
        self.MIN_NOTIFICATION_INTERVAL = 1.0  # Minimalny odstęp między powiadomieniami w sekundach
        if not self.webhook_url:
            print("Discord webhook URL not provided. Notifications will be disabled.")
        elif not self.webhook_url.startswith("https://discord.com/api/webhooks/"):
            print(f"Warning: Discord webhook URL '{self.webhook_url}' seems invalid.")


    def send_notification(self, message_content=None, embed=None):
        if not self.webhook_url:
            return

        # Dodaj powiadomienie do kolejki
        self.notification_queue.append({
            'message_content': message_content,
            'embed': embed,
            'timestamp': datetime.datetime.now()
        })
        self._process_queue()

    def _process_queue(self):
        """Przetwarza kolejkę powiadomień z uwzględnieniem limitów Discord"""
        if not self.notification_queue:
            return

        current_time = datetime.datetime.now()
        
        # Sprawdź czy minął wymagany odstęp czasowy
        if self.last_notification_time and \
           (current_time - self.last_notification_time).total_seconds() < self.MIN_NOTIFICATION_INTERVAL:
            return

        # Pobierz najstarsze powiadomienie z kolejki
        notification = self.notification_queue.pop(0)
        
        payload = {}
        if notification['message_content']:
            payload['content'] = notification['message_content']
        if notification['embed']:
            payload['embeds'] = [notification['embed']] if not isinstance(notification['embed'], list) else notification['embed']
        
        if not payload:
            return

        headers = {'Content-Type': 'application/json'}
        
        try:
            #print("wylaczone powiadomienia")
            response = requests.post(self.webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
            response.raise_for_status()
            self.last_notification_time = current_time
            print(f"Discord notification sent successfully. Queue size: {len(self.notification_queue)}")
        except requests.RequestException as e:
            print(f"Error sending Discord notification: {e}")
            # W przypadku błędu, wstaw powiadomienie z powrotem do kolejki
            self.notification_queue.insert(0, notification)
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")

    def _format_price(self, price):
        """Format price in standard way: with thousand separators and zł suffix"""
        if price is None:
            return "N/A"
        try:
            # First clean any existing formatting
            if isinstance(price, str):
                price = price.replace(' ', '').replace(',', '.').replace('zł', '').strip()
            price_float = float(price)
            if price_float.is_integer():
                return f"{int(price_float):,} zł".replace(",", " ")
            return f"{price_float:,.2f} zł".replace(",", " ").replace(".", ",")
        except (ValueError, TypeError):
            return str(price)

    def format_new_listing_embed(self, listing_data):
        embed = {
            "title": f":sparkles: New Listing: {listing_data.get('title', 'N/A')}",
            "url": listing_data.get('url'),
            "color": 0x00FF00, # Green
            "fields": [
                {"name": "Price", "value": self._format_price(listing_data.get('price')), "inline": True},
                {"name": "Site", "value": listing_data.get('site_name', 'N/A'), "inline": True},
                {"name": "Image Count", "value": str(listing_data.get('image_count', 'N/A')), "inline": True},
                {"name": "Description", "value": (listing_data.get('description', 'N/A')[:200] + '...') if listing_data.get('description') and len(listing_data.get('description', '')) > 200 else listing_data.get('description', 'N/A'), "inline": False},
            ],
            "timestamp": datetime.datetime.now().isoformat()
        }
        return embed

    def format_updated_listing_embed(self, listing_data, changes):
        # Filtruj tylko rzeczywiste zmiany (gdzie stara i nowa wartość są różne)
        real_changes = []
        for f, ov, nv in changes:
            if f == 'price' and self.ignore_identical_values and str(ov) == str(nv):
                continue
            if str(ov) != str(nv):
                real_changes.append((f, ov, nv))
        
        if not real_changes:
            return None

        title = f":arrows_counterclockwise: Updated Listing: {listing_data.get('title', 'N/A')}"
        fields = [
            {"name": "Site", "value": listing_data.get('site_name', 'N/A'), "inline": True},
            {"name": "URL", "value": f"[View Listing]({listing_data.get('url')})", "inline": False}
        ]
        
        change_descriptions = []
        for field, old_value, new_value in real_changes:
            # Formatowanie wartości liczbowych bez niepotrzebnych miejsc po przecinku
            if isinstance(old_value, float) and old_value.is_integer():
                old_value = int(old_value)
            if isinstance(new_value, float) and new_value.is_integer():
                new_value = int(new_value)
                
            # Formatowanie specjalne dla cen
            if field == 'price':
                formatted_old = self._format_price(old_value)
                formatted_new = self._format_price(new_value)
                change_desc = f"**{field.replace('_', ' ').title()}**: {formatted_old} → {formatted_new}"
                fields.append({
                    "name": "Price Change",
                    "value": f"**{formatted_old}** → **{formatted_new}**",
                    "inline": True
                })
            else:
                change_desc = f"**{field.replace('_', ' ').title()}**: `{old_value}` → `{new_value}`"
            change_descriptions.append(change_desc)


        embed = {
            "title": title,
            "url": listing_data.get('url'),
            "description": "\n".join(change_descriptions),
            "color": 0xFFA500, # Orange
            "fields": fields,
            "timestamp": datetime.datetime.now().isoformat()
        }
        return embed
