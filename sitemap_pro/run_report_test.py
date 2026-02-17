from app.report.generator import ReportGenerator
import os

# Find the most recent run
output_dir = "outputs"
runs = [os.path.join(output_dir, d) for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
if not runs:
    print("No runs found")
    exit(1)

latest_run_path = max(runs, key=os.path.getmtime)
latest_run = os.path.basename(latest_run_path)
print(f"Generating report for run: {latest_run}")

generator = ReportGenerator(latest_run)
if generator.generate():
    print(f"SUCCESS: Report generated at {generator.report_dir}/index.html")
else:
    print("FAIL: Report generation failed")
