import requests
from yelpapi import YelpAPI

# Replace with your own API keys
yelp_api_key = "YOUR_YELP_API_KEY"
yelp_secret = "YOUR_YELP_SECRET"

def get_restaurant_suggestions(location):
    url = f'https://api.yelp.com/v3/businesses/search?
        location={location}&
        limit=10'
    headers = {
        'Authorization': f'Bearer {yelp_api_key}'}
    response = requests.get(url, headers=headers)
    return response.json()

def main():
    location = input("Enter a location: ")
    suggestions = get_restaurant_suggestions(location)
    for suggestion in suggestions['businesses']:
        print(suggestion['name'])

if __name__ == '__main__':
    main()