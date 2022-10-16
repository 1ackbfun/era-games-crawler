# era-games-crawler

## Usage

### Install

```Bash
$ git clone https://github.com/1ackbfun/era-games-crawler.git
$ poetry install
```

### Test

```Bash
$ poetry run test
```

### Run Task

```Bash
$ poetry run task
```

### Cron

```Bash
$ crontab -e
```

Use your own path (maybe NOT `~/era-games-crawler`):

```
1 * * * * cd ~/era-games-crawler && poetry run task >/dev/null 2>&1
```
