
import nodriver as n
import asyncio
from pprint import pprint

async def main():
    print("STARTING BROWSER TO INSPECT TAB")
    try:
        browser = await n.start(headless=True)
        tab = await browser.get("about:blank")
        
        print("\n=== DIR(TAB) ===")
        pprint(dir(tab))
        
        print("\n=== DIR(BROWSER) ===")
        pprint(dir(browser))
        
        if hasattr(tab, 'connection'):
            print("\n=== Tab.connection ===")
            print(tab.connection)
        else:
            print("\nTab has no 'connection' attribute")
            
        if hasattr(tab, 'target'):
            print("\n=== Tab.target ===")
            print(tab.target)
            print(dir(tab.target))
            
        if hasattr(browser, 'connection'):
            print("\n=== Browser.connection ===")
            print(browser.connection)
            print(dir(browser.connection))

        # Try to find something that looks like send
        print("\n=== FINDING SEND METHODS ===")
        for attr in dir(tab):
            if 'send' in attr:
                print(f"tab.{attr}")
                
        browser.stop()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
