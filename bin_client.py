# coding: utf-8
import binascii
from datetime import datetime
import errno
import gzip
import json
import os
import ssl
import urllib.request
import urllib.parse

target_url = ""
PROXIES = {}
endian = ""

def settings():
    global target_url
    global PROXIES
    global endian
    
    settings = json.load(open("./json/settings.json", 'r', encoding='utf-8'))
    target_url = settings["target_url"]
    PROXIES = settings["proxies"]
    endian = settings["endian"]

def setup_proxy():
    proxy = urllib.request.ProxyHandler(PROXIES)
    opener = urllib.request.build_opener(proxy)
    urllib.request.install_opener(opener)

def save_bin(data: bytes):
    now = datetime.now()
    filename = "./submit_" + now.strftime("%Y%m%d_%H%M%S") + ".bin"
    with open(f"./{filename}", "xb") as fileobj:
        fileobj.write(data)
        print("\nバイナリデータをファイルに保存しました。\n")

def create_request(parameters: bytes):
    global target_url
    customHeaders = json.load(open('./json/http_headers.json', 'r'))
    # プロキシによっては、"Content-Encoding: gzip"エンティティヘッダとHTTPリクエストボディのgzipを
    # いい感じに解釈して、gzipを解凍して送信してしまうこともある(PacketProxy等)ため、注意。
    # Burp Suite のみ串挟めることを確認済
    req = urllib.request.Request(target_url, parameters, headers=customHeaders, method='POST')

    print("\n=== HTTP Request ===")
    print(str(req.method) + " " + str(req._full_url) + " HTTP/1.1") # Request-Line
    for key, val in req.headers.items():                            # headers
        print(key + ": " + val)
    print("\n" + str(req._data.decode('utf-8', 'replace')) + "\n")  # body

    return req

def get_response(req):
    # サーバが自己署名証明書で、無視したい時に利用(テスト用)
    ssl._create_default_https_context = ssl._create_unverified_context

    with urllib.request.urlopen(req) as res:
        # 雑処理直したい
        if res.version == 10:
            httpVer = "HTTP/1.0"
        elif res.version == 11:
            httpVer = "HTTP/1.1"
        else:
            # HTTP/2.0以降はurllibが対応してないのでエラーになる可能性あり
            # 2.0通信の場合、requests + hyperかhttpx等のライブラリ必要
            httpVer = str(res.version)
        print("\n=== HTTP Response ===")
        print(httpVer + " " + str(res.status) + " " + res.msg) # status line
        print(res.info())                                      # headers
        print(str(res.read().decode('utf-8', 'replace')))      # body

def pause():
    while 1:
        print("続行しますか？")
        judge = input("yes/no：")
        if judge == "yes" or judge == "y":
            break
        elif judge == "no" or judge == "n":
            print("プログラムを停止します")
            exit()
        else:
            print("yesかnoを入力してください")

def check_bin_length(data_type, bytelen_conf, binary_data):
    bytelen_text = len(binary_data)
    if bytelen_conf != bytelen_text:
        print(f"データ型：{data_type}")
        print(f"設定したバイト長{bytelen_conf}とバイナリデータのバイト長{bytelen_text}が一致しません")
        print(f"バイナリデータ：{binary_data}")
        pause()
    return binary_data

def translate_binary(filename: str):
    dataStr = json.load(open(filename, 'r', encoding='utf-8'))
    combined_bin = bytes(b'')

    for key in dataStr:
        dtype = dataStr[key][0]
        if dtype == "hex":
            combined_bin += check_bin_length(dataStr[key][0], dataStr[key][1],
                                        binascii.unhexlify(dataStr[key][2]))
        elif dtype == "int":
            if isinstance(dataStr[key][2], int):
                combined_bin += dataStr[key][2].to_bytes(dataStr[key][1], 'big')
            else:
                print(f"データ型{dtype}に対して、値{dataStr[key][2]}が整数ではありません")
                print("プログラムを停止します")
                exit()
        elif dtype == "Time_T":
            date_format = datetime.strptime(dataStr[key][2], "%Y/%m/%d %H:%M:%S")
            combined_bin += int(date_format.timestamp()).to_bytes(dataStr[key][1],'big')
        elif dtype == "ascii" or dtype == "str":
            combined_bin += check_bin_length(dataStr[key][0], dataStr[key][1],
                                        dataStr[key][2].encode('utf-8'))
        else:
            print(f"処理方法が未実装のデータ型です：{dtype}\njsonファイルを再確認してください")
            exit()
    
    return combined_bin

# CRC-16(CRC-16-CCITT)の計算、生成多項式：x^16+x^15+X^2+1
def crc16(data: bytes, ini: int, poly=0xa001):
    data = bytearray(data)
    crc = ini
    for b in data:
        cur_byte = 0xFF & b
        for _ in range(0, 8):
            # crcの最下位が1
            if (crc & 0x0001) ^ (cur_byte & 0x0001):
                # 右に1bitシフトし、生成多項式とXOR算
                crc = (crc >> 1) ^ poly
            else:
                # 右に1bitシフト
                crc >>= 1
            cur_byte >>= 1
    crc = (~crc & 0xffff)
    crc = (crc << 8) | ((crc >> 8) & 0xFF)
    #下位16bitが有効な計算値なので、0xffffでAND
    return crc & 0xffff

def main():
    settings()
    byte_str = bytes(b'')

    # プロキシON/OFF
    setup_proxy()

    # CRC計算、CRC-16
    # CRC = crc16(###binary###, 
    #             0xffff).to_bytes(2,'big')

    byte_str = translate_binary("./json/params.json")

    # バイトオーダー指定(Big Endian/Little Endian)
    if endian == "little":
        byte_str = byte_str[::-1]

    print(f"\n送信する16進2桁表現のbytesオブジェクト：\n{byte_str}")
    params = gzip.compress(byte_str)
    print(f"\nbytesオブジェクトのgzip圧縮：\n{params}")
    pause()

    # バイナリ保存ON/OFF
    # save_bin(byte_str)

    req = create_request(params)
    get_response(req)

if __name__ == '__main__':
    main()
