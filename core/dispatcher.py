# (c) 2015, Alice Ferrazzi <alice.ferrazzi@gmail.com>
#
# This file is part of Eisen
#
# Eisen is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Eisen is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Eisen.  If not, see <http://www.gnu.org/licenses/>.

import glob
from genericpath import isfile
from os.path import dirname, basename
import AnsibleV1Wrap
import core.AnsibleV1Inv as ans_inv
import ansible
import time
from sqlalchemy import *
from mysql_config import start_engine, sendTaskToDb
from bin import celery_work
# using global tasks_result dictionary for keeping the async result
from core import tasks_result
from core import tasks_package
from core import recepies_result
from core import recepies_package
from core import result2Db

engine , metadata = start_engine()
connection = engine.connect()

def ModulesList():
    """
    Get list of all available module:
    ansible

    :return: list
    """
    modules = glob.glob(dirname(__file__) + "/*.py")

    # remove itself for not reimporting
    dispatcher = (glob.glob(dirname(__file__) + "/dispatcher.py"))
    modules.remove(dispatcher[0])

    __all__ = [basename(f)[:-3] for f in modules if isfile(f)]
    # mod = {}
    # for i in __all__:
    #    print i
    #    mod[i]=(__import__('core.'+ i))
    return __all__

# return usable mod
# def installed_mod():
# return(mod)

#TODO make the Agent  Module be choosen using API
#update and only 1 agent module is needed
def AgentInfo(module=None):
    """

    :rtype: object
    """
    agents = []
    agent = {
        'id': 1,
        'module': 'Ansible',
        'version' : ansible.__version__,
    }
    agents.append(agent)
    return agents

def PackageUpdate(module=None):
    """

    :rtype: object
    """
    packs = []
    pack = {
        'id': 1,
        'command': 'Started',
    }
    packs.append(pack)
    return packs

def use_module():
    # API chooser
    module = AnsibleV1Wrap
    return module

def HostsList(module):
    hosts = module.HostsList()
    return hosts

def HostVarsList(module, id):
    vars = module.HostVarsList(id)
    return vars

def GroupVarsList(module, group):
    vars = module.GroupVarsList(group)
    return vars

def GroupsList(module):
    groups = module.GroupsList()
    return groups


def TasksList(module):
    """
    making the init example task
    :param module:
    :return: Json
    """
    #TODO (alice): maybe default task is a better name?
    tasks = module.TasksStart()
    return tasks

def RecipesList(module):
    """
    making the init example task
    :param module:
    :return: Json
    """
    #TODO (alice): maybe default task is a better name?
    recipes = module.RecipesStart()
    return recipes

def RunRecipe(module, playbook_file, id):
    """
    Run Task asyncronously
    """
    #retriving dynamic inventory from AnsibleInv
    inv = ans_inv.get_inv()
    #Starting async task and return
    recepies_result[id] = module.RunRecepie(inv, playbook_file)
    #result2Db[id] = ResultToDB(tasks_result[id], hosts, id)
    return recepies_result[id]

def ResultRecipe(id):
    """

    :param id:
    :return: String
    """
    # Cheking async task result
    try:
        if recepies_result[id] is False:
            return "not ready yet!"
        else:
            return recepies_result[id]
    except (Exception):
        return "not ready yet!"

def RunTask(module, hosts, command, mod, id):
    """
    Run Task asyncronously
    :param module:
    :param hosts:
    :param command:
    :param mod:
    :param id:
    :return: String
    """
    #retriving dynamic inventory from AnsibleInv
    inv = ans_inv.get_inv()
    #Starting async task and return
    tasks_result[id] = module.RunTask.delay(hosts, command, mod, inv)
    #result2Db[id] = ResultToDB(tasks_result[id], hosts, id)
    return tasks_result[id]

def ResultTask(id):
    """

    :param id:
    :return: String
    """
    # Cheking async task result
    try:
        if tasks_result[id].ready() is False:
            return "not ready yet!"
        else:
            return tasks_result[id].get()
    except (Exception):
        return "not ready yet!"

def ResultToDB(task, target_host, id):
    #sendTaskToDb(engine, metadata, connection, task, target_host)
    while task.ready() is False:
        time.sleep(1)
    tasks_result = str(task.get())
    #db.session.add(task_result(id, tasks_result, target_host))
    #db.session.commit()
    return 'done'

def PackageAction(module, hosts, command, mod, id, pack):
    """
    Run Task asyncronously
    :param module:
    :param hosts:
    :param command:
    :param mod:
    :param id:
    :return: String
    """
    #retriving dynamic inventory from AnsibleInv
    inv = ans_inv.get_inv()
    #Starting async task and return
    tasks_package[id] = module.RunTask.delay(hosts, command, mod, inv)
    while tasks_package[id].ready() is False:
        time.sleep(1)
    result_string = tasks_package[id].get()
    print ('result_string:'+str(result_string))
    print hosts
    connection = engine.connect()
    # try:
    package_result = Table('package_result', metadata, autoload=True,
                        autoload_with=engine)
    stmt = package_result.insert()
    import re
    pattern = re.compile("[\uD800-\uDFFF].", re.UNICODE)
    pattern = re.compile("[^\u0000-\uFFFF]", re.UNICODE)
    re_pattern = re.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', re.UNICODE)
    try:
        filtered_string = re_pattern.sub(u'\uFFFD', result_string['contacted'][hosts]['stdout'])
        if filtered_string == '' :
            filtered_string = result_string['contacted'][hosts]
    except:
        filtered_string = result_string['contacted'][hosts]
    try:
        result_short = result_string['contacted'][hosts]['module_args']
    except:
        result_short = result_string['contacted'][hosts]['invocation']['module_args']
    connection.execute(
        stmt,
        result_string=unicode(filtered_string),
        packageName=pack['packageName'],
        packageVersion=pack['packageVersion'],
        targetOS=pack['targetOS'],
        targetHost=pack['targetHost'],
        task_id=id,
        packageAction=pack['packageAction'],
        result_short=str(result_short),
    )
    connection.close()
    # except Exception, error:
    #     connection.close()
    #     print ('error:' + str(error))
    return result_string