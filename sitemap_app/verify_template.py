import sys
import os

# Ensure the app module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.comparison_viewer import ComparisonViewer

def test_generation():
    print("Initializing ComparisonViewer...")
    viewer = ComparisonViewer(template_dir="../app/templates")
    
    print("Generating HTML...")
    html = viewer.generate_comparison_html(
        web_capture="web.png",
        pdf_preview="pdf.png",
        web_text="This is web text.",
        pdf_text="This is pdf text.",
        comparison_result={
            "sync_rate": 98.5,
            "diff_count": 2,
            "diff_html": "<p>Diff</p>"
        },
        suggestions=[{"type": "text", "original": "a", "suggestion": "b"}]
    )
    
    print(f"Generated HTML length: {len(html)}")
    
    if "<!DOCTYPE html>" in html and "98.5%" in html:
        print("SUCCESS: HTML generated correctly.")
    else:
        print("FAILURE: HTML generation issues.")

if __name__ == "__main__":
    try:
        test_generation()
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()
