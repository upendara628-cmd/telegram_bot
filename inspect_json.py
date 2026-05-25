import re
import json

def inspect():
    with open("api_responses_extracted.txt", "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split the file by the "====" boundary line
    blocks = content.split("================================================================================")
    print(f"Total API response blocks: {len(blocks)}")
    
    for idx, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue
            
        # Find URL
        url_match = re.search(r'API RESPONSE JSON: GET (https?://\S+)', block)
        if url_match:
            url = url_match.group(1)
            print(f"\n[{idx+1}] URL: {url}")
            
            # Find Auth Header
            auth_match = re.search(r"Auth Headers: (\{.*?\})", block)
            if auth_match:
                print(f"   Auth Header found: {auth_match.group(1)[:200]}...")
                
            # Find JSON block
            json_start = block.find("JSON Snippet:\n")
            if json_start != -1:
                json_text = block[json_start + len("JSON Snippet:\n"):].strip()
                try:
                    # Clean any trailing lines/boundaries from json text
                    json_text = json_text.split("\n\n")[0].strip()
                    if json_text.endswith("... (truncated)"):
                        json_text = json_text[:-len("... (truncated)")].strip()
                    # Try to parse
                    data = json.loads(json_text)
                    print(f"   JSON Type: {type(data)}")
                    if isinstance(data, list):
                        print(f"   List Size: {len(data)}")
                        if data:
                            print("   Sample Item Keys:", list(data[0].keys()))
                            # Print a snippet of the first item
                            print("   Sample Item Data:")
                            print(json.dumps(data[0], indent=2)[:500])
                    elif isinstance(data, dict):
                        print("   Keys:", list(data.keys()))
                        print("   Sample Data:")
                        print(json.dumps(data, indent=2)[:500])
                except Exception as e:
                    print(f"   Could not parse JSON snippet: {e}")
                    # Print raw snippet text
                    print("   Raw Snippet:")
                    print(json_text[:300])

if __name__ == "__main__":
    inspect()
