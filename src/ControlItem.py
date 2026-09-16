#####################################################
#                                                   #
# Título do trabalho: Trabalho de Sockets           #
#         Disciplina: Redes de Computadores PPComp  #
#                                                   #
#####################################################

from Config import *
import queue

# Dicionário com os ambientes catalogados
global roomDict
roomDict = {}
# Dicionário com os tipos catalogados
global typeDict
typeDict = {}


# Objeto que mantém os dados de um ambiente
class RoomItem():
	roomID = ''    # ID do ambiente
	roomName = ''  # Nome do ambiente
	lampQueueList = {}
	actuatorQueueList = {}
	#runningStatus = False  # Possui thread monitorando?
	#thread = None          # Objeto da thread
	#eventObject = None     # Objeto de evento para cancelar o timeout

	# Inicializa com ID e Nome do ambiente
	def __init__(self, roomID, roomName):
		self.roomID = roomID
		self.roomName = roomName
		self.lampQueueList = {}
		self.actuatorQueueList = {}

	# Gerar a lista de lâmpadas do ambiente em formato texto
	def LampListToString(self):
		deviceList = []
		for deviceID in self.lampQueueList.keys():
			deviceList.append(f'{deviceID}')
		return ', '.join(deviceList)

	# Gerar a lista de ar-condicionados do ambiente em formato texto
	def ActuatorListToString(self):
		deviceList = []
		for deviceID in self.actuatorQueueList.keys():
			deviceList.append(f'{deviceID}')
		return ', '.join(deviceList)

	# Lista de lâmpadas do ambiente
	def toString(self):
		result = None
		if len(self.lampQueueList) > 0:
			result = f'[{self.roomID}] {self.roomName} => Lâmpadas> ' + self.LampListToString()
		if len(self.actuatorQueueList) > 0:
			if result is None:
				result = f'[{self.roomID}] {self.roomName} => '
			else:
				result += ' | '
			result += 'Ar-Condicionados> ' + self.ActuatorListToString()
		return result

	# Incluir nova lâmpada na lista
	def AddLamp(self, deviceID, lampQueue):
		print(f'Adicionando a lâmpada ID={deviceID} no ambiente {self.roomName}')
		self.lampQueueList.update({deviceID: lampQueue})

	# Remover uma lâmpada da lista
	def DelLamp(self, deviceID):
		print(f'Removendo a lâmpada ID={deviceID} do ambiente {self.roomName}')
		self.lampQueueList.pop(deviceID)
		return len(self.lampQueueList)

	# Incluir um ar-condicionado na lista do ambiente
	def AddActuator(self, deviceID, actuatorQueue):
		print(f'Adicionando o ar-condicionado ID={deviceID} no ambiente {self.roomName}')
		self.actuatorQueueList.update({deviceID: actuatorQueue})

	# Remover um ar-condicionado da lista do ambiente
	def DelActuator(self, deviceID):
		print(f'Removendo o ar-condicionado ID={deviceID} do ambiente {self.roomName}')
		self.actuatorQueueList.pop(deviceID)
		return len(self.actuatorQueueList)

	# Se um sensor foi acionado, interrompe o timeout e aciona as lâmpadas
	def Sensor(self, command):
		for deviceID, lampQueue in self.lampQueueList.items():
			lampQueue.put(int(command))

	# Envia um comando para todos os ar-condicionados do ambiente
	def CommandActuators(self, action):
		for deviceID, actuatorQueue in self.actuatorQueueList.items():
			actuatorQueue.put((int(action), TEMPERATURA_AR_CONDICIONADO))

# Objeto contendo os tipos catalogados
class TypeItem():
	typeID = ''    # ID do tipo
	typeCode = ''  # Código do tipo 'L' Lâmpada, 'S' Sensor de presença e 'T' Temperatura
	typeName = ''  # Nome do dispositivo

	def __init__(self, typeID, typeCode, typeName):
		self.typeID = typeID
		self.typeCode = typeCode
		self.typeName = typeName

# Formato da mensagem enviada pela fila para o controle geral
class MonitorItem():
	deviceID = None			# ID do dispositivo
	deviceTypeCode = None	# Código 'L' Lâmpada, 'S' Sensor de Presença ou 'A' Ar-Condicionado
	roomID = None			# ID do ambiente
	command = None			# Comando
							# Lâmpada:
							#	INCLUIR_LAMPADA / EXCLUIR_LAMPADA
							# Sensor de presença:
							#	PRESENCA_NAO_DETECTADA / PRESENCA_DETECTADA
							# Ar-Condicionado:
							#	INCLUIR_AR_CONDICIONADO / EXCLUIR_AR_CONDICIONADO
	lampQueue = None		# Fila para comunicação com a lâmpada / ar-condicionado

	def __init__(self, deviceID, deviceTypeCode, roomID, command, lampQueue):
		self.deviceID = deviceID
		self.deviceTypeCode = deviceTypeCode
		self.roomID = roomID
		self.command = command
		self.lampQueue = lampQueue

# Incluir um tipo no dicionário
def AddTypeItem(typeItem):
	global typeDict
	typeDict.update({ f'{typeItem.typeID}': typeItem})

# Obter um objeto de tipo pelo ID
def GetTypeItem(typeID):
	global typeDict
	if typeID in typeDict:
		return typeDict[typeID]
	return None

# Obter todo o dicionário de tipos
def GetTypeDict():
	global typeDict
	return typeDict

# Incluir um ambiente no dicionário
def AddRoomItem(roomItem):
	global roomDict
	roomDict.update({ f'{roomItem.roomID}': roomItem})

# Obter um objeto de ambiente pelo ID
def GetRoomItem(roomID):
	global roomDict
	if roomID in roomDict:
		return roomDict[roomID]
	return None

# Obter todo o dicionário de ambientes
def GetRoomDict():
	global roomDict
	return roomDict
