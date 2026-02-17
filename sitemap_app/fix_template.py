import os

file_path = "app/templates/comparison_view_new.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace placeholders with Jinja2 strings
# We construct the strings dynamically to avoid any tool-interception if possible
# But actually, writing {{ }} in python code is fine, as long as the tool doesn't modify python code logic.
# The tool issue seemed to be in `replace_file_content` logic when target/replacement had braces.

try:
    content = content.replace("__SYNC_RATE__", "{{ sync_rate }}")
    content = content.replace("__DIFF_COUNT__", "{{ diff_count }}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched template.")
except Exception as e:
    print(f"Error patching template: {e}")
