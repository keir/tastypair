import json
import re
from collections import defaultdict

def extract_ingredients_from_string(description):
  if description:
    cleaned_description = re.sub('[^a-z ]', '', description.lower())
    return cleaned_description.split()

def make_pairing_store():
  return defaultdict(lambda: defautdict(int))

def record_pairing(pairings, a, b):
  if a and b:
    pairings[a][b] += 1
    pairings[b][a] += 1

if __name__ == '__main__':
  num_items_seen = 10
  venues_with_menus = json.loads(open('menus.json').read())
  for venue in venues_with_menus:
    for menu in venue['menus']:
      for section in menu.get('sections', []):
        # todo: section['name']
        for subsection in section.get('subsections', []):
          # todo: subsection['name'] ?
          for item in subsection.get('contents', []):
            text_to_inspect_for_item = []
            text_to_inspect_for_item.append(item.get('name'))
            text_to_inspect_for_item.append(item.get('description'))
            for option_group in item.get('option_groups', []):
              text_to_inspect_for_item.append(option_group.get('text'))
              for option in option_group.get('options', []):
                text_to_inspect_for_item.append(option.get('name'))
            print json.dumps(map(extract_ingredients_from_string,
                                 text_to_inspect_for_item),
                             indent=2, sort_keys=True)
            num_items_seen += 1
            if num_items_seen == 20:
              import sys
              sys.exit(0)



  
