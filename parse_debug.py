import re
from html.parser import HTMLParser

class DebugHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.in_th = False
        
        self.current_table = []
        self.current_row = []
        self.current_cell = ""
        self.tables = []
        self.divs_with_pct = []
        self.current_div_classes = ""
        self.div_depth = 0
        self.pct_div_active = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'table':
            self.in_table = True
            self.current_table = []
            
        elif tag == 'tr' and self.in_table:
            self.in_tr = True
            self.current_row = []
            
        elif tag in ['td', 'th'] and self.in_tr:
            self.in_td = (tag == 'td')
            self.in_th = (tag == 'th')
            self.current_cell = ""
            
        elif tag == 'div':
            self.div_depth += 1
            if 'class' in attrs_dict:
                self.current_div_classes = attrs_dict['class']
            else:
                self.current_div_classes = ""

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
            self.tables.append(self.current_table)
            
        elif tag == 'tr' and self.in_table:
            self.in_tr = False
            self.current_table.append(self.current_row)
            
        elif tag in ['td', 'th'] and self.in_tr:
            self.in_td = False
            self.in_th = False
            self.current_row.append(self.current_cell.strip())
            
        elif tag == 'div':
            self.div_depth -= 1

    def handle_data(self, data):
        data_clean = data.strip()
        if not data_clean:
            return
            
        if (self.in_td or self.in_th) and self.in_tr:
            self.current_cell += data + " "
            
        # If we see a percentage sign in text outside tables, print context
        if '%' in data_clean:
            # Match number followed by %
            if re.search(r'\d+(?:\.\d+)?\s*%', data_clean):
                self.divs_with_pct.append((self.current_div_classes, data_clean))

def analyze_file(filename):
    print("\n" + "="*80)
    print(f"ANALYZING FILE: {filename}")
    print("="*80)
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        print(f"Could not open file: {e}")
        return
        
    parser = DebugHTMLParser()
    parser.feed(html_content)
    
    print(f"\nFound {len(parser.tables)} tables:")
    for idx, table in enumerate(parser.tables):
        print(f"\nTable {idx + 1} (Rows: {len(table)}):")
        # Print first 5 rows
        for r_idx, row in enumerate(table[:10]):
            print(f"  Row {r_idx + 1}: {row}")
        if len(table) > 10:
            print(f"  ... and {len(table) - 10} more rows")
            
    print(f"\nFound {len(parser.divs_with_pct)} divs/containers with percentage text:")
    for idx, (classes, text) in enumerate(parser.divs_with_pct[:15]):
        print(f"  {idx + 1}. Class: '{classes}' | Text: '{text}'")

if __name__ == "__main__":
    analyze_file("debug_timetable.html")
    analyze_file("debug_attendance.html")
    analyze_file("debug_dashboard.html")
