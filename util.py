import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random


@logger.catch
@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3), reraise=True)
def request_post(url, headers=None, data=None, json=None, stream=True,verify=False, timeout=(5, 5)):
    return requests.post(
        url,
        stream=stream,
        verify=verify,
        timeout=timeout, 
        headers=headers,
        data=data,
        json=json,
    )

@logger.catch
@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3),reraise=True)
def request_get(url, params=None, headers=None, stream=False,verify=False, timeout=(5, 5)):
    return requests.get(
        url, 
        params=params,
        headers=headers,
        stream=stream,
        verify=verify,
        timeout=timeout,
    )