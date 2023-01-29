# 이미지 업로드 슬랙봇 with lambda (SAM)

> 이미지를 업로드하면 lambda 함수를 호출하고 이미지 태그를 반환해줍니다.

- Runtime: python3.9

## SAM 빌드 & 배포

- 빌드, 배포

```shell
$ sam build --use-container && sam deploy --config-env staging
```

- 스테이징 배포

```shell
$ sam deploy --config-env staging
```

- 빌드

```shell
$ sam deploy
```

---

## package 추가

### requirements.txt에 패키지 추가

1. pip install {패키지} 를 사용하여 패키지를 추가했다면, 아래 명령어로 requirements.txt 를 새로 생성합니다.

```shell
$ pip freeze > require$ents.txt
```

2. /requirements.txt 의 내용을 복사하여 /src/requirements.txt 에 붙여넣습니다. (lambda에서 적용되기 위함.)

### Lambda Layer에 패키지 추가

1. ./python-lib 디렉토리 생성, 하위에 python 디렉토리를 생성합니다.

2. 아래 명령어를 실행하여 추가할 패키지 설치 혹은 requirements.txt 의 패키지를 모두 설치합니다.

```shell
# 1. 특정 패키지 설치
$ pip install {추가할 패키지} -t ./python-lib/python
# 2. 패키지 모두 설치
$ pip install -r requirements.txt -t ./python-lib/python
```

3. 구조가 아래와 같다면, python-lib 디렉토리를 압축합니다.

```
python-lib
  ㄴpython
    ㄴdotenv
    ㄴrequests
    ㄴ ...
    ㄴ ...
```

4. 압축한 package 파일을 lambda layer에 추가, 변경합니다.

---

## environment 추가

- lambda 함수 > 구성 > 환경변수 탭에서 추가, 변경 가능합니다.
