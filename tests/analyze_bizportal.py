from bs4 import BeautifulSoup
import re

try:
    with open('bizportal.html', 'rb') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    # Find element with text ~75.4...
    # Regex for 75.4...
    element = soup.find(string=re.compile(r"75\.4"))
    if element:
        parent = element.parent
        print(f"Found price in: {parent.name}, Class: {parent.get('class')}")
        print(f"Parent Parent Class: {parent.parent.get('class')}")
        # Print a snippet of the parent
        print(f"HTML: {parent}")
    else:
        print("Not found via regex")

except Exception as e:
    print(f"Error: {e}")
