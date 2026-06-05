import os
import sys

try:
    import google.adk
except ImportError:
    print("Error: google-adk package is not installed in this Python environment.")
    print("Please activate your virtual environment first.")
    sys.exit(1)

adk_dir = os.path.dirname(google.adk.__file__)
js_path = os.path.join(adk_dir, "cli", "browser", "main-3CUQG2IN.js")

if not os.path.exists(js_path):
    print(f"Error: Minified JS bundle not found at: {js_path}")
    sys.exit(1)

target = 'getTextContent(e){if(!e)return"";let A=e.indexOf(",");if(A===-1)return"";let t=e.substring(A+1);try{return atob(t)}catch(n){return"Failed to decode text content"}}'
replacement = 'getTextContent(e){if(!e)return"";let A=e.indexOf(",");if(A===-1)return"";let t=e.substring(A+1);try{return decodeURIComponent(escape(atob(t)))}catch(n){return"Failed to decode text content"}}'

try:
    with open(js_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    target_count = content.count(target)
    replacement_count = content.count(replacement)

    print(f"File: {js_path}")
    print(f"Found {target_count} occurrences of target (unpatched) string.")
    print(f"Found {replacement_count} occurrences of replacement (patched) string.")

    if target_count == 0:
        if replacement_count > 0:
            print("Patch is already applied.")
            sys.exit(0)
        else:
            print("Error: Target string not found in the file, and patch is not applied. The JS bundle version might be different.")
            sys.exit(1)

    new_content = content.replace(target, replacement)

    # Attempt to write it back
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("Successfully patched ADK CLI Browser bundle.")
    sys.exit(0)

except Exception as e:
    print(f"Error applying patch: {e}")
    sys.exit(1)
