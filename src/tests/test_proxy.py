import requests

from src.settings import Settings

def test_scrapeops_api(api_key, test_url="https://httpbin.org/ip"):
    """Test ScrapeOps API connectivity"""
    
    scrapeops_url = "https://proxy.scrapeops.io/v1/"
    
    params = {
        'api_key': api_key,
        'url': test_url,
    }
    
    try:
        response = requests.get(scrapeops_url, params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content: {response.text[:500]}")
        
        if response.ok:
            print("✅ ScrapeOps API is working correctly")
            return True
        else:
            print("❌ ScrapeOps API request failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing ScrapeOps API: {e}")
        return False

# Test the API
if __name__ == "__main__":
    api_key =  Settings.PROXY_API
    test_scrapeops_api(api_key)