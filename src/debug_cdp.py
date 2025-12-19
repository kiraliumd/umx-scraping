
from nodriver import cdp
import asyncio

async def main():
    print("DEBUGGING CDP TYPES")
    
    # Check what set_extra_http_headers returns
    headers = {"test": "header"}
    cmd_headers = cdp.network.set_extra_http_headers(headers=headers)
    print(f"set_extra_http_headers type: {type(cmd_headers)}")
    print(f"set_extra_http_headers value: {cmd_headers}")
    
    # Check set_cookie
    cmd_cookie = cdp.network.set_cookie(name="test", value="123", url="http://example.com")
    print(f"set_cookie type: {type(cmd_cookie)}")
    print(f"set_cookie value: {cmd_cookie}")
    
    # Iterate if generator
    if hasattr(cmd_cookie, '__iter__'):
        print("Iterating...")
        try:
            for i in cmd_cookie:
                print(f"Yield: {type(i)} - {i}")
        except Exception as e:
            print(f"Iteration error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
