#####################################################
#                                                   #
# Título do trabalho: Trabalho de Sockets           #
#         Disciplina: Redes de Computadores PPComp  #
#                                                   #
#####################################################

from Config import *
from ControlItem import *
from Device import *
from datetime import datetime
import struct
import ctypes

def unixTimeStamp():
	return datetime.timestamp(datetime.now())

#[datahora_unpacked] = struct.unpack('!d', datahora_packed)
#datahora = datetime.datetime.fromtimestamp(datahora_unpacked)	

# Estrutura compartilhada por todas as mensagens
class Message():
	code = None		# 1 byte - unsigned char 
	dateTime = None	# 8 bytes - double - Timestamp da mensagem
	subject = None	# Descrição do tipo de mensagem
	mask = ''		# Máscara usada para obter os dados da mensagem

	def __init__(self):
		self.code = 0
		self.dateTime = 0.0
		self.subject = ''
		self.mask = ''

	def size(self):
		return struct.calcsize(self.mask)

	def toString(self):
		dateTime = datetime.fromtimestamp(self.dateTime)
		dateTimeStr = dateTime.strftime("%m/%d/%Y, %H:%M:%S")
		return f"[{dateTimeStr}] {self.code}: {self.subject}, " + self.toStringMsg()

	def toStringMsg(self):
		pass

	def pack(self):
		pass

	def unpack(self):
		pass

class MessageStatus(Message):

	# Campos da mensagem
	deviceID = None	# 4 bytes - unsigned int
	status = None	# 2 bytes - unsigned short
	strStatus = [	'[1] Dispositivo foi registrado',
					'[2] Valor de leitura recebido',
					'[3] Ação executada',
					'[4] Dispositivo ainda não registrado',
					'[5] Tipo de dispositivo não suportado',
					'[6] Formato de mensagem inválida',
					'[7] Ambiente selecionado inválido',
					'[8] ID de dispositivo inválido',
					'[9] Ação não suportada',
					'[10] Mensagem não esperada',
					'[11] Falha de rede'
				]

	def __init__(self):
		self.code = MSG_STATUS
		self.mask = '!BdIH'
		self.subject = 'Status'

	def toStringMsg(self):
		if(self.deviceID != None and self.status != None):
			return f"Dispositivo: {self.deviceID}, Status: " + self.strStatus[self.status-1]
		else:
			return 'Mensagem não inicializada'

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# I unsigned int
	# H unsigned short
	# Funcao de empacotamento de mensagem
	def pack(self, deviceID, status):
		self.dateTime = unixTimeStamp()
		self.deviceID = deviceID
		self.status = status
		return struct.pack(self.mask, self.code, self.dateTime, self.deviceID, self.status)

	def unpack(self, msg):
		code, self.dateTime, self.deviceID, self.status = struct.unpack(self.mask, msg)

class MessageRegister(Message):

	# Campos da mensagem
	deviceType = None	# 1 byte - unsigned char
						# 1 = Lâmpada
						# 2 = Sensor de Presença
						# 3 = Termômetro

	def __init__(self):
		self.code = MSG_REGISTRO
		self.mask = '!BdB'
		self.subject = 'Registro'

	def toStringMsg(self):
		if(self.deviceType != None):
			return f"Tipo de dispositivo: {self.deviceType}"
		else:
			return 'Mensagem não inicializada'

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# B unsigned char (devTipo)
	# Funcao de empacotamento de mensagem
	def pack(self, deviceType):
		self.dateTime = unixTimeStamp()
		self.deviceType = deviceType
		return  struct.pack(self.mask, self.code, self.dateTime, self.deviceType)

	def unpack(self, msg):
		code, self.dateTime, self.deviceType = struct.unpack(self.mask, msg)

class MessageList(Message):
	# Campos da mensagem
	countRooms = None	# 2 bytes - unsigned shot
	roomDict = {}

	def __init__(self):
		self.code = MSG_LISTA_AMBIENTES
		self.mask = '!BdH'
		self.maskRoom = '!H20s'
		self.subject = 'Lista de Ambientes'

	def toStringMsg(self):
		if(self.countRooms != None):
			rooms = []
			for roomID, roomItem in self.roomDict.items():
				rooms.append(f'{roomItem.roomID}: {roomItem.roomName}')
			strRooms = '; '.join(rooms)
			return f"Ambientes [{self.countRooms}]: {strRooms}"
		else:
			return "Mensagem não inicializada"

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# H unsigned short (numAmbientes)
	# H unsigned short (numAmbiente[1])
	# 10s string (nomeAmbiente[1]
	# ...
	# H unsigned short (numAmbiente[N])
	# 10s string (nomeAmbiente[N]
	# Funcao de empacotamento de mensagem
	def pack(self, roomDict):
		self.dateTime = unixTimeStamp()
		self.countRooms = len(roomDict)
		self.roomDict = roomDict
		size = self.size() + self.countRooms * struct.calcsize(self.maskRoom)
		listBuffer = ctypes.create_string_buffer(size)
		struct.pack_into(self.mask, listBuffer, 0, self.code, self.dateTime, self.countRooms)
		offset = self.size()
		for roomID, roomItem in roomDict.items():
			intRoomID = int(roomID)
			struct.pack_into(self.maskRoom, listBuffer, offset, intRoomID, roomItem.roomName.encode('UTF-8'))
			offset += struct.calcsize(self.maskRoom)
		return listBuffer[:]

	def unpack(self, msg):
		code, self.dateTime, self.countRooms = struct.unpack(self.mask, msg[:self.size()])
		self.roomDict = {}
		sizeItem = struct.calcsize(self.maskRoom)
		msg = msg[self.size():]
		tmp = msg[:sizeItem]
		for cont in range(self.countRooms):
			roomID, roomName = struct.unpack(self.maskRoom, tmp)
			# O nome do ambiente ocupa um campo de tamanho fixo (20 bytes) e vem
			# preenchido com '\x00' à direita. Removemos esses caracteres nulos
			# para que a lista seja exibida corretamente no terminal.
			roomName = roomName.decode('UTF-8').replace('\x00', '').strip()
			msg = msg[sizeItem:]
			tmp = msg[:sizeItem]
			roomItem = RoomItem(roomID, roomName)
			self.roomDict.update( { f'{roomID}': roomItem } )

class MessageSelect(Message):

	# Campos da mensagem
	roomID = None	# 2 bytes - unsigned short

	def __init__(self):
		self.code = MSG_SELECIONA_AMBIENTE
		self.mask = '!BdH'
		self.subject = 'Seleciona Ambiente'

	def toStringMsg(self):
		if(self.roomID != None):
			return f"Ambiente selecionado: {self.roomID}"
		else:
			return 'Mensagem não inicializada'

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# H unsigned short (ambID)
	# Funcao de empacotamento de mensagem
	def pack(self, roomID):
		self.dateTime = unixTimeStamp()
		self.roomID = roomID
		return  struct.pack(self.mask, self.code, self.dateTime, self.roomID)

	def unpack(self, msg):
		code, self.dateTime, self.roomID = struct.unpack(self.mask, msg)

class MessageSensor(Message):

	# Campos da mensagem
	deviceID = None	# 4 bytes - unsigned int
	value = None	# 4 bytes - float

	def __init__(self):
		self.code = MSG_SENSOR
		self.mask = '!BdIf'
		self.subject = 'Leitura'

	def toStringMsg(self):
		if(self.deviceID != None and self.value != None):
			return f"Dispositivo: {self.deviceID}, Valor do sensor: {self.value}"
		else:
			return 'Mensagem não inicializada'

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# I unsigned int (devID)
	# f float (valor)
	# Funcao de empacotamento de mensagem
	def pack(self, deviceID, value):
		self.dateTime = unixTimeStamp()
		self.deviceID = deviceID
		self.value = value
		return struct.pack(self.mask, self.code, self.dateTime, self.deviceID, self.value)

	def unpack(self, msg):
		code, self.dateTime, self.deviceID, self.value = struct.unpack(self.mask, msg)

class MessageLamp(Message):

	# Campos da mensagem
	deviceID = None	# 4 bytes - unsigned int
	action = None		# 1 byte - unsigned char
						# 0 = Desligar
						# 1 = Ligar

	def __init__(self):
		self.code = MSG_LAMPADA
		self.mask = '!BdIB'
		self.subject = 'Atuador'

	def toStringMsg(self):
		if(self.deviceID != None and self.action != None):
			if self.action == LUZ_APAGADA:
				return f"Ação: {self.action} (Apagar Luz)"
			if self.action == LUZ_ACESA:
				return f"Ação: {self.action} (Acender Luz)"
			else:
				return f"Ação: {self.action} (Desconhecida)"
		else:
			return 'Mensagem não inicializada'

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# I unsigned int (devID)
	# B unsigned char (acao)
	# Funcao de empacotamento de mensagem
	def pack(self, deviceID, action):
		self.dateTime = unixTimeStamp()
		self.deviceID = deviceID
		self.action = action
		return struct.pack(self.mask, self.code, self.dateTime, self.deviceID, self.action)

	def unpack(self, msg):
		code, self.dateTime, self.deviceID, self.action = struct.unpack(self.mask, msg)

class MessageAirConditioner(Message):

	# Campos da mensagem
	deviceID = None	# 4 bytes - unsigned int
	action = None		# 1 byte - unsigned char
						# 0 = Desligar
						# 1 = Ligar
	value = None		# 4 bytes - float (temperatura alvo, usada ao ligar)

	def __init__(self):
		self.code = MSG_AR_CONDICIONADO
		self.mask = '!BdIBf'
		self.subject = 'Atuador Ar-Condicionado'

	def toStringMsg(self):
		if(self.deviceID != None and self.action != None and self.value != None):
			if self.action == AC_DESLIGAR:
				return f"Ação: {self.action} (Desligar Ar-Condicionado)"
			if self.action == AC_LIGAR:
				return f"Ação: {self.action} (Ligar Ar-Condicionado, temperatura alvo {self.value}°C)"
			else:
				return f"Ação: {self.action} (Desconhecida)"
		else:
			return 'Mensagem não inicializada'

	# ! network (= big-endian)
	# B unsigned char (codigo)
	# d double (datahora)
	# I unsigned int (devID)
	# B unsigned char (acao)
	# f float (temperatura alvo)
	def pack(self, deviceID, action, value):
		self.dateTime = unixTimeStamp()
		self.deviceID = deviceID
		self.action = action
		self.value = value
		return struct.pack(self.mask, self.code, self.dateTime, self.deviceID, self.action, self.value)

	def unpack(self, msg):
		code, self.dateTime, self.deviceID, self.action, self.value = struct.unpack(self.mask, msg)

# cria um objeto contendo a primeira mensagem do buffer
# retorna (1) None se não existir uma mensagem completa ou buffer vazio
#         (2) o que restou no buffer após retirar a primeira mensagem
def getMessage(buffer):
	msg = None
	#O código está no primeiro byte
	codeBin = buffer[:1]
	if len(codeBin) == 1:
		code, = struct.unpack('!B', codeBin)
		if code >= 1 and code <= 7:
			# tamanho de cada tipo de mensagem
			msgsSize = [15,10,11,11,17,14,18]
			msgSize = msgsSize[code-1]
			# Se o buffer não contém nem o tamanho-base da mensagem, aguarda
			# mais bytes antes de tentar decodificar (evita struct.error em
			# mensagens parcialmente recebidas, inclusive a Lista de Ambientes)
			if len(buffer) < msgSize:
				return None, buffer
			# caso especial, mensagem com a lista possui tamanho variável
			if code == MSG_LISTA_AMBIENTES:
				cod,dat,countRooms = struct.unpack('!BdH', buffer[:11])
				msgSize += countRooms * 22
				# Se ainda faltam os itens da lista, aguarda mais bytes
				if len(buffer) < msgSize:
					return None, buffer
			# copia a mensagem do buffer
			msgData = buffer[:msgSize]
			# remove do buffer a mensagem que foi copiada
			buffer = buffer[msgSize:]
			# cria o objeto de acordo com o código da mensagem
			if code == MSG_STATUS:
				msg = MessageStatus()
			if code == MSG_REGISTRO:
				msg = MessageRegister()
			if code == MSG_LISTA_AMBIENTES:
				msg = MessageList()
			if code == MSG_SELECIONA_AMBIENTE:
				msg = MessageSelect()
			if code == MSG_SENSOR:
				msg = MessageSensor()
			if code == MSG_LAMPADA:
				msg = MessageLamp()
			if code == MSG_AR_CONDICIONADO:
				msg = MessageAirConditioner()
			# decodifica a mensagem recebida
			msg.unpack(msgData)
		else:
			# Código desconhecido: descartamos apenas o byte inválido e
			# avisamos. No código original a thread caía com AttributeError
			# no print abaixo, encerrando a conexão sem tratamento adequado.
			print('>>> Código inválido (' + str(code) + '), descartando byte e continuando...')
			buffer = buffer[1:]
			return None, buffer
	return msg, buffer

# Recebe uma mensagem e retorna o objeto com os dados
def ReceiveMessage(connection, device):
	print('>>> Aguardando mensagem')
	while True:
		# (1) Se o buffer está vazio, aguarda a chegada de dados.
		if not device.buffer or len(device.buffer) == 0:
			try:
				device.buffer = connection.recv(TAM_BUFFER)
			except OSError:
				# Ex.: WinError 10054 - conexão encerrada à força pelo cliente.
				# Antes a thread do servidor caía com uma exceção não tratada.
				print('>>> Falha de rede ao receber dados. Encerrando conexão.')
				connection.close()
				return None
			if not device.buffer:
				# conexão encerrada de forma ordenada pelo cliente
				connection.close()
				return None
		# (2) Tenta extrair todas as mensagens completas que existem no buffer.
		#     getMessage pode devolver a mensagem, descartar byte(s) inválido(s)
		#     (o buffer diminui) ou indicar que a mensagem está incompleta.
		while len(device.buffer) > 0:
			nBytes = len(device.buffer)
			print('>>> Decodificando mensagem...')
			msg, device.buffer = getMessage(device.buffer)
			if msg != None:
				return msg
			if len(device.buffer) == 0 or len(device.buffer) >= nBytes:
				break  # nada mais a extrair sem receber novos bytes
		# (3) Uma mensagem ficou incompleta (ou o buffer se esgotou).
		#     Recebe mais dados e tenta decodificar novamente no próximo laço.
		try:
			dataBin = connection.recv(TAM_BUFFER)
		except OSError:
			print('>>> Falha de rede ao receber dados. Encerrando conexão.')
			connection.close()
			return None
		if not dataBin:
			connection.close()
			return None
		device.buffer = device.buffer + dataBin
	return None
