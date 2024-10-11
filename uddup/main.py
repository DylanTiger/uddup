#!/usr/bin/python
# coding=utf-8
import argparse
import sys
import os
import re
from urllib.parse import urlparse
import concurrent.futures
import threading

# Check if we are running this on windows platform
is_windows = sys.platform.startswith('win')

# Console Colors
if is_windows:
    G = '\033[92m'  # green
    Y = '\033[93m'  # yellow
    W = '\033[0m'   # white
    try:
        import win_unicode_console, colorama
        win_unicode_console.enable()
        colorama.init()
    except:
        G = Y = W = ''
else:
    G = '\033[92m'  # green
    Y = '\033[93m'  # yellow
    W = '\033[0m'   # white


def banner():
    print(r"""%s
  _   _ ____      _             
 | | | |  _ \  __| |_   _ _ __  
 | | | | | | |/ _` | | | | '_ \ 
 | |_| | |_| | (_| | |_| | |_) |
  \___/|____/ \__,_|\__,_| .__/ 
                         |_|    

              %s# Coded By @2RS3C
    %s""" % (Y, G, W))


def file_arg(path):
    if not os.path.isfile(path):
        raise ValueError
    return path


def get_ignored_suffixes():
    return (
        'css', 'js', 'gif', 'jpg', 'png', 'jpeg', 'svg', 'xml', 'txt', 'json', 
        'ico', 'webp', 'otf', 'ttf', 'woff', 'woff2', 'eot', 'swf', 'zip', 
        'pdf', 'doc', 'ppt', 'docx', 'xls', 'xlsx', 'ogg', 'mp4', 'mp3', 'mov'
    )


def get_web_suffixes():
    return (
        'htm', 'html', 'xhtml', 'shtml', 'jhtml', 'cfm', 'jsp', 'jspx', 
        'wss', 'action', 'php', 'php4', 'php5', 'py', 'rb', 'pl', 'do', 
        'xml', 'rss', 'cgi', 'axd', 'asx', 'asmx', 'ashx', 'asp', 'aspx', 'dll'
    )


def get_existing_pattern_urls(purl, uurls):
    results = []
    url_path = get_url_path(purl)
    path_parts = url_path.split('/')

    if len(path_parts) == 1:
        return results

    url_pattern = '/'.join(path_parts[:-1])
    url_schema = purl.scheme
    url_hostname = purl.hostname

    for uurl in uurls:
        if uurl.scheme != url_schema or uurl.hostname != url_hostname:
            continue

        uurl_path = get_url_path(uurl)
        if uurl_path.startswith(url_pattern):
            results.append(uurl)

    return results


def get_query_params_keys(parsed_url_query):
    keys = []
    qparams = parsed_url_query.split('&')
    for q in qparams:
        keys.append(q.split('=')[0])
    return keys


def is_all_params_exists(old_pattern, new_pattern):
    old_params_keys = get_query_params_keys(old_pattern.query)
    new_params_keys = get_query_params_keys(new_pattern.query)

    for k in old_params_keys:
        if k not in new_params_keys:
            return False
    return True


def has_more_params(old_pattern, new_pattern):
    old_params_keys = get_query_params_keys(old_pattern.query)
    new_params_keys = get_query_params_keys(new_pattern.query)
    return len(new_params_keys) > len(old_params_keys)


def get_url_path(purl):
    return purl.path.strip('/')


def process_url_batch(urls, web_suffixes, ignored_suffixes, filter_path):
    thread_local_urls = set()

    for url in urls:
        url = url.rstrip()
        if not url:
            continue

        parsed_url = urlparse(url)
        url_path = get_url_path(parsed_url)

        if not url_path:
            thread_local_urls.add(parsed_url)
            continue

        if url_path.endswith(ignored_suffixes):
            continue

        if filter_path and re.search(filter_path, url_path):
            continue

        if url_path.endswith(web_suffixes):
            thread_local_urls.add(parsed_url)
            continue

        existing_pattern_urls = get_existing_pattern_urls(parsed_url, thread_local_urls)
        if not existing_pattern_urls:
            thread_local_urls.add(parsed_url)
        elif parsed_url.query:
            for u in existing_pattern_urls:
                if not u.query:
                    thread_local_urls.remove(u)
                    thread_local_urls.add(parsed_url)
                    continue

                if is_all_params_exists(u, parsed_url):
                    if has_more_params(u, parsed_url):
                        thread_local_urls.remove(u)
                        thread_local_urls.add(parsed_url)
                    continue
                else:
                    thread_local_urls.add(parsed_url)
                    continue

    return thread_local_urls


def main(urls, output, silent, filter_path):
    unique_urls = set()
    lock = threading.Lock()

    if not silent:
        banner()

    web_suffixes = get_web_suffixes()
    ignored_suffixes = get_ignored_suffixes()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Process URLs in batches
        batch_size = 100  # Tune this based on performance and task size
        futures = [
            executor.submit(process_url_batch, urls[i:i + batch_size], web_suffixes, ignored_suffixes, filter_path)
            for i in range(0, len(urls), batch_size)
        ]

        for future in concurrent.futures.as_completed(futures):
            thread_local_urls = future.result()
            # Lock only when updating the global unique_urls set
            with lock:
                unique_urls.update(thread_local_urls)

    print_results(unique_urls, output)
    return unique_urls


def print_results(uurls, output):
    if output:
        try:
            with open(output, "w") as f:
                for url in sorted(uurls):
                    u = url.geturl()
                    f.write(u + "\n")
                    print(u)
        except:
            print('[X] Failed to save the output to a file.')
    else:
        for url in sorted(uurls):
            u = url.geturl()
            print(u)


def interactive():
    parser = argparse.ArgumentParser(description='Remove URL pattern duplications.')

    # Detect if input is from pipe
    if not sys.stdin.isatty():
        urls = sys.stdin.read().splitlines()
        silent = True
        output = None
        filter_path = None
    else:
        parser.add_argument('-u', '--urls', help='File with a list of URLs.', type=file_arg, dest='urls_file', required=True)
        parser.add_argument('-o', '--output', help='Save results to a file.', dest='output')
        parser.add_argument('-s', '--silent', help='Print only the result URLs.', action='store_true', dest='silent')
        parser.add_argument('-fp', '--filter-path', help='Filter paths by a given Regex.', dest='filter_path')
        args = parser.parse_args()

        silent = args.silent
        output = args.output
        filter_path = args.filter_path

        with open(args.urls_file, 'r', encoding="utf-8") as f:
            urls = f.readlines()

    main(urls, output, silent, filter_path)


if __name__ == "__main__":
    interactive()
