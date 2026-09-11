import json

with open('dashboard_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Read the HTML template and inject data
with open('可视化大屏_template.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('__DATA__', json.dumps(data, ensure_ascii=False))

with open('可视化大屏.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Done! 可视化大屏.html generated')
