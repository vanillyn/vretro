import requests

from src.data.config import VRetroConfig

config = VRetroConfig.load()
CLIENT_ID = config.igdb_client_id
CLIENT_SECRET = config.igdb_client_secret


def get_access_token():
    auth_url = f"https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials"
    response = requests.post(auth_url)
    return response.json().get("access_token")


def get_game_data(game_name):
    token = get_access_token()
    if not token:
        print("Failed to retrieve access token.")
        return

    url = "https://api.igdb.com/v4/games"
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain",
    }

    query = f'fields name, first_release_date, involved_companies.company.name, platforms.name, cover.url, summary, genres.name; search "{game_name}"; limit 50;'

    response = requests.post(url, headers=headers, data=query)

    if response.status_code == 200:
        data = response.json()
        if data:
            game = data[0]
            print(f"Title: {game.get('name')}")
            print(f"Description: {game.get('summary', 'No description available.')}\n")

            if "screenshots" in game:
                print("Screenshots:")
                for ss in game["screenshots"]:
                    url = "https:" + ss["url"].replace("t_thumb", "t_720p")
                    print(f"- {url}")
            else:
                print("No screenshots found.")
        else:
            print("No game found with that title.")
    else:
        print(f"Error: {response.status_code} - {response.text}")


get_game_data("The Legend of Zelda: Tears of the Kingdom")
