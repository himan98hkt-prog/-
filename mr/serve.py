#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""화성 확인 화면 띄우기 (지시서 9장 2단계).

    python3 serve.py --catalog ./catalog
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description='화성 확인 화면 서버')
    ap.add_argument('--catalog', default='catalog', help='카탈로그 디렉터리 (기본: ./catalog)')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()

    import uvicorn
    from server.app import create_app

    app = create_app(a.catalog)
    print(f'카탈로그: {os.path.abspath(a.catalog)}')
    print(f'화성 확인 화면: http://{a.host}:{a.port}/')
    uvicorn.run(app, host=a.host, port=a.port, log_level='warning')


if __name__ == '__main__':
    main()
