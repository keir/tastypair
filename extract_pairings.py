import json
import re
import sys
from collections import defaultdict

def extract_ingredients_from_string(description):
  if description:
    cleaned_description = re.sub('[^a-z ]', '', description.lower())
    return [item for item in cleaned_description.split() if item]
  return []

def make_pairing_store():
  return dict(pairings=defaultdict(lambda: defaultdict(int)),
              ingredients=defaultdict(int),
              total_ingredients=0,
              total_pairings=0)

def record_pairing(pairing_store, a, b):
  pairing_store['total_pairings'] += 1
  if a and b:
    pairing_store['pairings'][a][b] += 1
    pairing_store['pairings'][b][a] += 1

def add_paired_ingredients_to_pairing_store(pairing_store, paired_items):
  for i, item_1 in enumerate(paired_items):
    pairing_store['total_ingredients'] += 1
    pairing_store['ingredients'][item_1] += 1
    for item_2 in paired_items[i + 1:]:
      record_pairing(pairing_store, item_1, item_2)

if __name__ == '__main__':
  pairing_store = make_pairing_store()
  num_items_seen = 10
  venues_with_menus = json.loads(open('menus.json').read())
  for venue in venues_with_menus:
    if not venue.get('menus'):
      print >> sys.stderr, 'Missing menus:', venue.get('name'), venue.get('hash_id')
    for menu in venue.get('menus', []):
      for section in menu.get('sections', []):
        # Maybe: use section['name']
        for subsection in section.get('subsections', []):
          # Maybe: use subsection['name']
          for item in subsection.get('contents', []):
            text_to_inspect_for_item = []
            text_to_inspect_for_item.append(item.get('name'))
            text_to_inspect_for_item.append(item.get('description'))
            for option_group in item.get('option_groups', []):
              text_to_inspect_for_item.append(option_group.get('text'))
              for option in option_group.get('options', []):
                text_to_inspect_for_item.append(option.get('name'))
            ingredients_list = map(extract_ingredients_from_string,
                                   text_to_inspect_for_item)
            combined_ingredients = set()
            map(combined_ingredients.update, ingredients_list)
            combined_ingredients = list(combined_ingredients)
            add_paired_ingredients_to_pairing_store(pairing_store,
                                                    combined_ingredients)
            num_items_seen += 1
  print json.dumps(pairing_store, indent=2, sort_keys=True)
  
