import os
import requests
from bs4 import BeautifulSoup
import lxml
import pendulum


class Utils:

    @staticmethod
    def init() -> None:
        cache_path = r'./cache'
        if not os.path.exists(cache_path):
            os.mkdir(cache_path)
        return

    @staticmethod
    def jst_to_cst(jst_str: str) -> str:
        jst_str = jst_str.replace('㈪', ' Monday')
        jst_str = jst_str.replace('㈫', ' Tuesday')
        jst_str = jst_str.replace('㈬', ' Wednesday')
        jst_str = jst_str.replace('㈭', ' Thursday')
        jst_str = jst_str.replace('㈮', ' Friday')
        jst_str = jst_str.replace('㈯', ' Saturday')
        jst_str = jst_str.replace('㈰', ' Sunday')
        jst_time = pendulum.from_format(
            jst_str, 'YY/MM/DD dddd HH:mm:ss', tz='Asia/Tokyo')
        cst_time = jst_time.in_timezone('Asia/Shanghai')
        return cst_time.format('YYYY-MM-DD HH:mm:ss')

    @staticmethod
    def get_timestamp(time_str: str) -> int:
        cst_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        return cst_time.int_timestamp

    @staticmethod
    def now(is_timestamp: bool = False) -> str | int:
        current = pendulum.now('Asia/Shanghai')
        if is_timestamp:
            return current.int_timestamp
        else:
            return current.format('YYYY-MM-DD HH:mm:ss')

    @staticmethod
    def in_last_hour(time_str: str) -> bool:
        target_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        last_hour = pendulum.today(
            'Asia/Shanghai').add(hours=pendulum.now('Asia/Shanghai').hour)
        return (target_time - last_hour).seconds >= 0

    @staticmethod
    def in_last_week(time_str: str) -> bool:
        target_time = pendulum.from_format(
            time_str, 'YYYY-MM-DD HH:mm:ss', tz='Asia/Shanghai')
        last_week = pendulum.today('Asia/Shanghai').subtract(days=7)
        return (target_time - last_week).seconds >= 0


class EraGameSpider:

    @staticmethod
    def get_html(url: str, use_cache: bool = False) -> str:
        html_text = ''
        if use_cache:
            cache_file = './cache/' + url.replace('://', '_').replace('/', '_')
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    html_text = f.read()
                print(f'{Utils.now()}  [INFO] 已读取缓存 {cache_file}')
            except Exception as e:
                print(f'{Utils.now()}  [WARN] {e}')
                resp = requests.get(url, auth=('era', 'era'))
                if resp.status_code == 200:
                    with open(cache_file, 'wb') as f:
                        f.write(resp._content)
                    print(f'{Utils.now()}  [INFO] 已重新缓存 {cache_file}')
                    html_text = resp._content.decode('utf-8')
                else:
                    print(f'{Utils.now()} [ERROR] 请求 {url} 失败')
        else:
            resp = requests.get(url, auth=('era', 'era'))
            if resp.status_code == 200:
                html_text = resp._content.decode('utf-8')
                print(f'{Utils.now()}  [INFO] 请求 {url} 成功')
            else:
                print(f'{Utils.now()} [ERROR] 请求 {url} 失败')
        return html_text

    @staticmethod
    def check_update(url: str) -> list:
        html = EraGameSpider.get_html(f'{url}/index.html', True)
        soup = BeautifulSoup(html, 'lxml')
        page_result = []
        for table_content in soup.select('table#table'):
            # print(table_content.prettify())
            for row_data in table_content.find_all('tr'):
                raw_data = row_data.find_all('td')
                if raw_data[3].text != 'サイズ':
                    page_result.append({
                        'url': f"{url}/{raw_data[1].find('a')['href']}",
                        'file_id': raw_data[1].find('a').text,
                        'file_name': raw_data[7].text,
                        'size': raw_data[3].text,
                        'time': Utils.jst_to_cst(raw_data[4].text),
                        'desc': raw_data[2].text,
                    })
        latest_result = []
        for item in reversed(page_result):
            if Utils.in_last_hour(item['time']):
                # if Utils.in_last_week(item['time']):
                latest_result.append(item)
        return latest_result

    @staticmethod
    def broadcast(news: list) -> None:
        if len(news) > 0:
            print(f'{Utils.now()}  [INFO] 最近更新({len(news)}作):')
            for el in news:
                print()
                print(el['file_id'], el['url'])
                print(f'{el["file_name"]} ({el["size"]}) 更新于 {el["time"]}')
                print(el['desc'])
        else:
            print(f'{Utils.now()}  [INFO] 没有更新')
        return


def main() -> None:
    Utils.init()
    for path in ['up', 'up2']:
        res = EraGameSpider.check_update(f'http://book-shelf-end.com/{path}')
        EraGameSpider.broadcast(res)
        print()


if __name__ == '__main__':
    main()
