import requests
import json
import datetime # Added import for datetime

class NotificationManager:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        if not self.webhook_url:
            print("Discord webhook URL not provided. Notifications will be disabled.")
        elif not self.webhook_url.startswith("https://discord.com/api/webhooks/"):
            print(f"Warning: Discord webhook URL '{self.webhook_url}' seems invalid.")


    def send_notification(self, message_content=None, embed=None):
        if not self.webhook_url:
            # print(f"Notification (disabled): {message_content or embed}")
            return

        payload = {}
        if message_content:
            payload['content'] = message_content
        if embed:
            payload['embeds'] = [embed] if not isinstance(embed, list) else embed
        
        if not payload:
            print("Notification attempted with no content or embed.")
            return

        headers = {'Content-Type': 'application/json'}
        
        try:
            print("wylaczone powiadomienia")
            #response = requests.post(self.webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
            #response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            # print(f"Discord notification sent successfully. Message: {message_content or 'Embed used'}")
        except requests.RequestException as e:
            print(f"Error sending Discord notification: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
        except Exception as e:
            print(f"An unexpected error occurred while sending Discord notification: {e}")

    def format_new_listing_embed(self, listing_data):
        embed = {
            "title": f":sparkles: New Listing: {listing_data.get('title', 'N/A')}",
            "url": listing_data.get('url'),
            "color": 0x00FF00, # Green
            "fields": [
                {"name": "Price", "value": str(listing_data.get('price', 'N/A')), "inline": True},
                {"name": "Site", "value": listing_data.get('site_name', 'N/A'), "inline": True},
                {"name": "Image Count", "value": str(listing_data.get('image_count', 'N/A')), "inline": True},
                {"name": "Description", "value": (listing_data.get('description', 'N/A')[:200] + '...') if listing_data.get('description') and len(listing_data.get('description', '')) > 200 else listing_data.get('description', 'N/A'), "inline": False},
            ],
            "timestamp": datetime.datetime.now().isoformat()
        }
        return embed

    def format_updated_listing_embed(self, listing_data, changes):
        # Filtruj tylko rzeczywiste zmiany (gdzie stara i nowa wartość są różne)
        real_changes = [(f, ov, nv) for f, ov, nv in changes if str(ov) != str(nv)]
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
                
            change_desc = f"**{field.replace('_', ' ').title()}**: `{old_value}` → `{new_value}`"
            change_descriptions.append(change_desc)
            # Dodaj szczegółowe pola dla ważnych zmian
            if field == 'price':
                fields.append({
                    "name": "Price Change",
                    "value": f"`{old_value} zł` → `{new_value} zł`",
                    "inline": True
                })


        embed = {
            "title": title,
            "url": listing_data.get('url'),
            "description": "\n".join(change_descriptions),
            "color": 0xFFA500, # Orange
            "fields": fields,
            "timestamp": datetime.datetime.now().isoformat()
        }
        return embed
