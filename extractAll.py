import sys
import os
import re
import json
import shutil
import string
import random
from subprocess import run, TimeoutExpired, DEVNULL

dirNamePattern = re.compile(r'(?:(?P<name>.*) - )?(?P<matricule>\w+)(?:@(?P<domain>ecam.be|student.ecam.be)(?: (?P<day>\d{2})-(?P<month>\d{2})-(?P<year>\d{4}) (?P<hour>\d{2})_(?P<minute>\d{2})_(?P<second>\d{2}))?)?')

class BadArchive(Exception):
	def __init__(self, path):
		self.__path = path

	@property
	def path(self):
		return self.__path

	def __str__(self):
		return 'Unable to extract from {}'.format(self.path)

def getRandomString(length):
	letters = string.ascii_lowercase
	res = ''.join(random.choice(letters) for i in range(length))
	return res

def findFreeName(root, prefix, extension=None):
	if extension is not None and len(extension) > 0 and not extension.startswith('.'):
		extension = '.' + extension

	if extension is None:
		extension = ''

	res = prefix + extension
	index = 2
	while(os.path.exists(os.path.join(root, res))):
		res = prefix + '_' + str(index) + extension
		index+=1
	
	return os.path.join(root, res)

def parseDirName(dirName):
	result = dirNamePattern.match(dirName)
	
	if result is None:
		raise ValueError('Unable to parse {}'.format(dirName))
	
	return result.groupdict()

def formatInfo(rawInfo):
	res = {
		'name': rawInfo['name'],
		'matricule': rawInfo['matricule']
	}

	if 'domain' in rawInfo:
		email = '{}@{}'.format(rawInfo['matricule'], rawInfo['domain'])
	else:
		email = '{}@ecam.be'.format(rawInfo['matricule'])

	res['email'] = email

	if 'hour' in rawInfo:
		res['datetime'] = f"{rawInfo['day']}/{rawInfo['month']}/{rawInfo['year']} {rawInfo['hour']}:{rawInfo['minute']}:{rawInfo['second']}"

	return res

def moveAllFile(src, dst):
	content = os.listdir(src)
	try:
		for name in content:
			shutil.move(os.path.join(src, name), dst)
	except Exception as e:
		print('Problem while moving {}. Is longPath enabled ?'.format(os.path.join(src, name)))
		raise e

def getStudentWorkspace(submitDir, workspace):
	file = findFile(submitDir, ['.py', '.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tgz'])

	if file.endswith('.py'):
		moveAllFile(os.path.dirname(file), workspace)

	else:
		extractDir = findFreeName(submitDir, 'extract')
		os.mkdir(extractDir)
		extractArchive(file, extractDir)
		getStudentWorkspace(extractDir, workspace)

def processSubmitDir(submitDir, workspaces, jsonContent):
	data = formatInfo(parseDirName(os.path.basename(submitDir)))
	studentDir = os.path.join(workspaces, data['matricule'])
	checkDirectory(studentDir, createIt=True)
	workspace = findFreeName(studentDir, 'workspace')
	os.mkdir(workspace)
	data['workspace'] = workspace
	data['comment'] = []

	def handleError():
		print('ERROR with {} ({}):\n   {}\n'.format(data['matricule'], data['name'], data['comment'].join('\n   ')))
		moveAllFile(submitDir, workspace)

	try:
		getStudentWorkspace(submitDir, workspace)
	except FileNotFoundError as e:
		data['comment'].append('No python file found')
		handleError()
	except BadArchive as e:
		data['comment'].append(str(e))
		handleError()

	comment = data['comment']
	if 'comment' in jsonContent:
		comment += jsonContent['comment']
	data.update(jsonContent)
	data['comment'] = comment

	reportPath = findFreeName(studentDir, 'report', 'json')
	with open(reportPath, 'x', encoding='utf8') as file:
		json.dump(data, file, indent='\t', ensure_ascii=False)

def extractArchive(archiveFile, extractDir):
	try:
		res = run(['7z', 'x', archiveFile, f'-o{os.path.abspath(extractDir)}'], stdout=DEVNULL, stderr=DEVNULL)
		if res.returncode != 0:
			raise Exception()
	except:
		raise BadArchive(archiveFile)

def findFile(inDir, extensions):
	for root, _, files in os.walk(inDir):
		for extension in extensions:
			for file in files:
				if file.endswith(extension):
					return os.path.join(root, file)
	raise FileNotFoundError('no {} file found in {}'.format(extensions, inDir))

def listDir(inDir):
	return filter(lambda file: os.path.isdir(os.path.join(inDir, file)) ,os.listdir(inDir))

def checkDirectory(path, createIt=False, clearIt=False):
	res = os.path.exists(path)
	if res:
		if clearIt:
			response = input('{} already exists ! delete it ? (y/n)'.format(path))
			if response == 'y':
				shutil.rmtree(path)
			else:
				print('Abort')
				exit(0)
	else:
		if createIt:
			os.mkdir(path)
			res = True

	return res

def start(zipPath, extractDir, workspaces, jsonPath):
	checkDirectory(extractDir, clearIt=True)
	checkDirectory(workspaces, createIt=True)
	extractArchive(zipPath, extractDir)

	with open(jsonPath, encoding='utf8') as file:
		jsonContent = json.load(file)

	for dirName in listDir(extractDir):
		processSubmitDir(os.path.join(extractDir, dirName), workspaces, jsonContent)

if __name__ == '__main__':
	if len(sys.argv) < 4:
		print('Usage: extractAll workDir zip json')
		exit(0)
	
	workDir = sys.argv[1]
	zipPath = sys.argv[2]
	jsonPath = sys.argv[3]
	extractDir = os.path.join(workDir, os.path.basename(zipPath).split('.')[0])
	workspaces = os.path.join(workDir, 'workspaces')
	start(zipPath, extractDir, workspaces, jsonPath)