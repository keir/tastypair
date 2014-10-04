#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2014 GoDaddy Inc.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Author: mierle@gmail.com (Keir Mierle)

import argparse
import httplib
import json
import sys
import time
import urllib2

ENDPOINT_URL = 'https://api.locu.com/v2/venue/search/'
API_KEY = None

def log(*args):
  sys.stderr.write(' '.join(args) + '\n')

def make_curl_command(query_json):
  return "curl -X POST %s -d '%s' | formatjson" % (ENDPOINT_URL, query_json)

def search(query):
  """Run the given query, expressed as a Locu Venue Search object, with the
  default API key. Attempts to retry a small number of times in the case of
  failure, to prevent transient errors from breaking everything."""
  query['api_key'] = API_KEY
  query_json = json.dumps(query, sort_keys=True, indent=2)
  max_retries = 3
  # The Internet is unreliable, and even Locu can sometimes have an occasional
  # failed request, so make the script robust to transient errors by retrying a
  # couple of times if there is an error when fetching.
  for retry in range(max_retries):
    try:
      response_json = urllib2.urlopen(
          urllib2.Request(ENDPOINT_URL, query_json)).read()
      return json.loads(response_json)
    except KeyboardInterrupt:
      log('\nGot keyboard interrupt; bailing.')
      sys.exit(1)
    except:
      # On error, dump a command so the breaking query can be cut and pasted
      # into a terminal to retry.
      log('ERROR: Failed POST; command:')
      log(make_curl_command(query_json))
      if retry == max_retries - 1:
        log('Too many retries; dying out entirely.')
        raise
      else:
        log('Retrying...')

def query_for_venues_with_menus(args):
  return {
    "fields": [
      "locu_id",
      "locu.last_modified",
    ],
    "venue_queries": [
      {
        "location" : {
          "locality" : "San Mateo",
          "country" : "United States",
        },
        "menus" : {
          "$present" : True
        }
      }
    ]
  }

def get_venues_for_query(create_query):
  """Gets all the venues for the given query, using paginated search. This can
  handle queries returning ~500,000 or more. The matching venues are returend
  as a set of Locu IDs."""

  # Turn on Locu's venue result set functionality which uses pagiantion to get
  # many venues over several requests. When only the Locu ID is requested, much
  # larger result sets can be requested (up to e.g. 2000 venues at a time).
  create_query['results_key'] = 'create'
  create_query['limit'] = 2000

  log('Query:')
  log(make_curl_command(json.dumps(create_query, indent=2)))

  venue_ids = set()
  result = None
  start = time.time()
  request_number = 0
  max_latency = 0
  total_venues = 0
  while True:
    if not result:
      # Start a new result set.
      result = search(create_query)
      expected_results = result.get('total', -1)
      if expected_results != -1:
        # Not all API keys support returning totals.
        log('Expected results: %d' % expected_results)
    else:
      # Result set already started; get the next page.
      result = search({'results_key': result['next_results_key']})

    # Track latency and number of venues; everyone likes watching grass grow.
    latency = time.time() - start
    max_latency = max(latency, max_latency)
    total_venues += len(result['venues'])
    venue_ids.update(venue['locu_id'] for venue in result['venues'])
    log('%5d: %3d results in %0.2f seconds '
          '(max so far %0.2f; unique %8d; total venues %8d)' % (
        request_number,
        len(result['venues']),
        latency,
        max_latency,
        len(venue_ids),
        total_venues))
    start = time.time()
    request_number += 1

    if not len(result['venues']):
      log('Got an empty result set indicating no more pages; finished.')
      break

  log('Expected results: %d' % expected_results)

  return venue_ids

def venues_for_args(args):
  """Yields all the venues for the given """
  venues = set(get_venues_for_query(query_for_venues_with_menus(args)))
  total = len(venues)

  log('Done getting list of venues to fetch; now fetching venue details.')

  num_venues_fetched = 0

  # To guard against the case that there are venues that vanish from the API,
  # track how many times the below loop makes no progress.
  num_times_no_progress_made = 0
  
  # This loop is the second stage, which fetches the venue details a few at a
  # time. Locu's API supports fetching many (thousands) of venues at once, but
  # only if you are getting just the matching Locu IDs. To get details, you
  # have to do query for a handful of the venues at a time. Also, the Locu API
  # may not always return exactly the venues you requested, so this code is
  # robust to the case that the returned set does not contain all the requested
  # venues.
  while venues:
    num_venues_left = len(venues)
    venues_to_fetch = {venues.pop()
                       for x in range(min(args.num_venues_per_detail_batch,
                                          len(venues)))}
    result = search({
      'fields': [
        'name',
        'location',
        'contact',
        'menus',
      ],
      'venue_queries': [dict(locu_id=locu_id) for locu_id in venues_to_fetch]
    })

    venues_fetched = set()
    for venue in result['venues']:
      # Mark the venues returned so they are not fetched again.
      if venue['locu_id'] in venues_to_fetch:
        venues_to_fetch.remove(venue['locu_id'])
      else:
        # This can happen if a venue was marked as a duplicate between the time
        # the list of Locu IDs to fetch was retrieved, and the time the details
        # for that venue is requested. In that case, subtract out the redirect.
        redirected_from_venue = venue.get('redirected_from')
        if type(redirected_from_venue) == list:
          assert len(redirected_from_venue) == 1
          redirected_from_venue = redirected_from_venue[0]
        if redirected_from_venue and redirected_from_venue in venues:
          # Good; this is a redirect from a venue we were looking for.
          venues_to_fetch.remove(redirected_from_venue)
        else:
          # Weird; log and export it to the XML anyway.
          log('Got unexpected venue: %s (%s)' % (venue['name'],
                                                 venue['locu_id']))

      yield venue
      num_venues_fetched += 1

    # Add back any venues that didn't get sent in the response.
    venues.update(venues_to_fetch)

    log('Venues fetched so far: %3d / %d (%0.1f%%)' % (
        (total - len(venues)), total, 100 * (1.0 - len(venues) / float(total))))

    if num_venues_left == len(venues):
      # No progress; maybe bail.
      num_times_no_progress_made += 1
      if num_times_no_progress_made >= args.max_no_progress_rounds:
        log('ERROR: Retried too many times when not making progress')
        log('There are', num_venues_left, 'venues remaining.')
        log('Bailing, but dumping what we got so far.')
        break

  log('Fetched %s venues.' % num_venues_fetched)

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--num-venues-per-detail-batch', default=50, type=int,
                      help=('Maximum number of venues to fetch per batch '
                            'when fetching the venue details'))
  parser.add_argument('--max-no-progress-rounds', default=5, type=int,
                      help=('Maximum number of times to try fetching a batch '
                            'when no new venues are found; if this is exceeded,'
                            ' abort the current fetch and dump whatever was '
                            'fetched so far.'))
  parser.add_argument('--output', default='menus.json')
  parser.add_argument('--api-key')
  args = parser.parse_args()
  API_KEY = args.api_key
  with open(args.output, 'w') as outfile:
    print 'Writing to:', args.output
    outfile.write(json.dumps([venue for venue in venues_for_args(args)],
                             sort_keys=True,
                             indent=2))
