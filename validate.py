import httpx
import asyncio

async def test_endpoint(client, name, url):
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code == 200:
            print(f"✅ {name} ({url}) -> Success")
        else:
            print(f"❌ {name} ({url}) -> Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ {name} ({url}) -> Exception: {e}")

async def main():
    gateway_url = "http://localhost:8000"
    endpoints = [
        ("Inventory Service", f"{gateway_url}/api/v1/inventory"),
        ("Shipments Service", f"{gateway_url}/api/v1/shipments"),
        ("Compliance Service", f"{gateway_url}/api/v1/compliance"),
        ("Purchase Order Service", f"{gateway_url}/api/v1/purchase-orders"),
        ("Auth Service", f"{gateway_url}/api/v1/auth"),
        ("Supplier Risk Service", f"{gateway_url}/api/v1/supplier-risk/analyze"),
    ]

    print(f"Testing API Gateway at {gateway_url}...")
    
    async with httpx.AsyncClient() as client:
        # Check if gateway is up
        try:
            res = await client.get(f"{gateway_url}/health")
            if res.status_code == 200:
                print("✅ API Gateway is UP")
            else:
                print("❌ API Gateway returned error status")
        except Exception:
            print("❌ API Gateway is DOWN. Please ensure it is running.")
            return

        print("\nTesting Microservices via Gateway:")
        for name, url in endpoints:
            await test_endpoint(client, name, url)

if __name__ == "__main__":
    asyncio.run(main())
