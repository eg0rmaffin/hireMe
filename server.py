import http.server
import socketserver
import urllib.parse
import os
import requests


from dotenv import load_dotenv
load_dotenv()


client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")

if not all([client_id, client_secret, redirect_uri]):
    raise ValueError("CLIENT_ID, CLIENT_SECRET или REDIRECT_URI отсутствуют в файле .env")

# Опциональный параметр state для предотвращения CSRF атак
state = 'your_state_value'  # можно сгенерировать случайное значение для каждого запроса

authorize_url = f"https://hh.ru/oauth/authorize?response_type=code&client_id={client_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&state={state}"

print("Перейдите по следующему URL для авторизации:")
print(authorize_url)

# Обработчик HTTP-запросов
class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)

        if 'code' in query:
            authorization_code = query['code'][0]
            print(f"Authorization code received: {authorization_code}")

            # Обмен authorization code на токен доступа
            token_url = "https://hh.ru/oauth/token"
            data = {
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'client_secret': client_secret,
                'code': authorization_code,
                'redirect_uri': redirect_uri
            }

            response = requests.post(token_url, data=data)
            response_data = response.json()

            if response.status_code == 200:
                access_token = response_data['access_token']
                print(f"Access token: {access_token}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorization successful!")
            else:
                print(f"Error getting access token: {response_data}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Authorization failed.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization code not found.")

PORT = 5000

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print(f"Serving at port {PORT}")
    httpd.serve_forever()
