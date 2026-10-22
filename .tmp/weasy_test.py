from weasyprint import HTML
html = """<html><head><style>@page{size:A4;margin:2cm}</style></head><body>
<h1>FoodLoop ID</h1>
<svg xmlns="http://www.w3.org/2000/svg" width="500" height="200" viewBox="0 0 500 200">
<rect x="10" y="100" width="40" height="80" fill="#0284c7"/>
<rect x="70" y="60" width="40" height="120" fill="#16a34a"/>
<text x="10" y="195" font-size="12" fill="#0c4a6e">Jan</text>
</svg>
<p>Total 120 kg</p>
</body></html>"""
pdf = HTML(string=html).write_pdf()
open(".tmp/weasy_test.pdf","wb").write(pdf)
print("PDF OK bytes:", len(pdf))
