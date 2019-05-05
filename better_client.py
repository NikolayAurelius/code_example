from requests import get, post
from requests.exceptions import ConnectionError
from time import sleep
from hashlib import sha512
import functools
import json
import client.constants as c
from client.skills import skills
import platform
from datetime import datetime as dt


def increasingly_delay(start, final, steps):
    step = (final - start) // steps + 1
    for delay in range(start, final + 1, step):
        yield delay


def error(msg, type_error, xtbl=False):
    pass


def wait_connection(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start, final, attempts = c.START_DELAY_ATTEMPTS, c.FINAL_DELAY_ATTEMPTS, c.MAX_ATTEMPTS
        for delay in increasingly_delay(start, final, attempts):
            try:
                return func(*args, **kwargs)
            except ConnectionError:
                sleep(delay)
                # TODO: Логируем инфу о том, что было рассоединение

        # TODO: Логируем инфу о том, что не дождались соединения и закрываем программу
    return wrapper


@wait_connection
def do_get(url, params=None):
    #print('get', url)
    return get(url, params)


@wait_connection
def do_post(url, data=None, json=None):
    return post(url, data, json)


def from_b(s):
    text = ''
    for c in s:
        text += f'{c}:'
    return text


def get_hash(iterable):
    return from_b(sha512("_".join(iterable).encode()).digest())


class Worker:
    def __init__(self, host, machine):
        self.host = host
        # Информация о клиенте, нужна для идентификации на сервере
        self.unique = get_hash(machine['unique'])
        self.regular = get_hash(machine['regular'])

        self.task_queue = []
        self.methods_address = f'http://{self.host}/methods'
        self.results = []
        self.skills = skills  # TODO: Здесь объявить скиллы func_name:func_obj
        self.objects = {}
        self.bets = []

    def get_new_tasks(self):
        response = do_get(f'{self.methods_address}/get_new_tasks?v={c.V}&unique={self.unique}&regular={self.regular}')
        try:
            # TODO: Может вылететь неучтённое исключение
            tasks = response.json()
        except (ValueError, AttributeError) as er:
            # TODO: Логировать, что есть трабла с json
            return False
        #print('tasks from server', tasks)
        for task in tasks:
            self.task_queue.append(task)
        return True

    def drop_result(self, result):
        print('result in drop', result)
        do_post(f'{self.methods_address}/drop_result', json=json.dumps(result))
        return True

    def solve(self, task):
        skill = self.skills[task['skill']]
        try:
            success, result = skill(self, *task['args'], **task['kwargs'])
        except Exception as er:
            success, result = False, str(er)
            print('SOLVE ERROR', er, '\n', skill, '\n', task)
            self.driver.quit()
            self.task_queue[0] = {'skill': 'init_driver', 'args': [], 'kwargs': {}, 'attempts': 3}


        #print('result in solve', result)
        if success:
            self.task_queue.pop(self.task_queue.index(task))
            return result
        task['attempts'] -= 1
        if task['attempts'] == 0:
            self.task_queue.pop(self.task_queue.index(task))
        # TODO: Если несколько раз не получилось решить, то удалять задачу и отчитываться об этом на сервер
        return result

    def _work(self):
        for task in self.task_queue[:]:
            task['result'] = self.solve(task)
            self.drop_result(task)

        self.get_new_tasks()

    def work(self):
        while True:
            print('tasks', self.task_queue)
            print('length tasks', len(self.task_queue))
            print('bets', self.bets)
            self._work()
            sleep(c.WORK_DELAY)

# TODO: взять уникальные и регулярные данные о клиенте через os/sys

# TODO: Декоратор сбора статы (время исполнения) со скиллов и функция/метод сохранения статы на клиенте и отправки на сервер

task_signature = {'id': int(0), 'skill': 'func_name',
                  'args': 'args', 'kwargs': 'kwargs',
                  'attempts': 0}


def just_skill(worker, *args, **kwargs):
    pass
    """
    try:
        return True, f(*args, **kwargs)
    except SomeException as er:
        Логирование
        return False, None
    """
machine = {'unique': platform.uname(), 'regular': [str(dt.now())]}

worker = Worker(c.HOST, machine)

worker.work()
