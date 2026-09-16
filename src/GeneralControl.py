#####################################################
#                                                   #
# Título do trabalho: Trabalho de Sockets           #
#         Disciplina: Redes de Computadores PPComp  #
#                                                   #
#####################################################

from Config import *
from ControlItem import *
import queue
import threading

# Dicionário de timers de desligamento automático, por ambiente
roomTimers = {}

def TurnOffRoom(roomItem):
	"""Chamado quando o tempo de ausência de movimento se esgota."""
	print(f'>>> Timer: sem movimento em [{roomItem.roomID}] {roomItem.roomName} por {TEMPO_LUZ_ACESA}s. Desligando lâmpadas e ar-condicionados.')
	roomItem.Sensor(LUZ_APAGADA)
	roomItem.CommandActuators(AC_DESLIGAR)

def GeneralControl(controlQueue, roomsList, typesList):
	# Dicionário contendo todos os ambientes cadastrados
	for item in roomsList:
		roomID = item['roomID']
		roomName = item['roomName']
		AddRoomItem(RoomItem(roomID, roomName))
	# Dicionário com os tipos carregados da tabela de configuração
	for item in typesList:
		typeID = item['typeID']
		typeCode = item['typeCode']
		typeName = item['typeName']
		AddTypeItem(TypeItem(typeID, typeCode, typeName))
	while True:
		# Aguarda a chegada de um comando na fila
		monitorItem = controlQueue.get()
		print(f'Comando chegando na fila do controle do ambiente {monitorItem.roomID}')
		roomItem = GetRoomItem(monitorItem.roomID)
		# Se encontrou o ambiente na lista, executa o comando
		if roomItem != None:
			# Atende o comando de acordo com o tipo de dispositivo
			# LAMPADA <- Registrar ou desregistrar no sistema
			if monitorItem.deviceTypeCode == COD_LAMPADA:
				# Registrar a lâmpada
				if monitorItem.command == INCLUIR_LAMPADA:
					roomItem.AddLamp(monitorItem.deviceID, monitorItem.lampQueue)
				# Desregistrar a lâmpada
				if monitorItem.command == EXCLUIR_LAMPADA:
					roomItem.DelLamp(monitorItem.deviceID)

			# AR-CONDICIONADO <- Registrar ou desregistrar no sistema
			if monitorItem.deviceTypeCode == COD_AR_CONDICIONADO:
				if monitorItem.command == INCLUIR_AR_CONDICIONADO:
					roomItem.AddActuator(monitorItem.deviceID, monitorItem.lampQueue)
				if monitorItem.command == EXCLUIR_AR_CONDICIONADO:
					roomItem.DelActuator(monitorItem.deviceID)

			# SENSOR DE PRESENÇA <- Indica que o sinal foi recebido, acionar lâmpadas e AC
			if monitorItem.deviceTypeCode == COD_SENSOR_PRESENCA:
				command = int(monitorItem.command)
				# Se presença detectada: aciona lâmpadas, envia comando para ar-condicionado
				# e programa o desligamento automático. Se ausência, desliga tudo.
				if command == PRESENCA_DETECTADA:
					roomItem.Sensor(command)
					roomItem.CommandActuators(AC_LIGAR)
					# Cancela timer anterior deste ambiente e agenda novo desligamento
					previousTimer = roomTimers.pop(monitorItem.roomID, None)
					if previousTimer is not None:
						previousTimer.cancel()
					newTimer = threading.Timer(TEMPO_LUZ_ACESA, TurnOffRoom, args=[roomItem])
					newTimer.daemon = True
					newTimer.start()
					roomTimers[monitorItem.roomID] = newTimer
				else:
					# Ausência de movimento -> apaga tudo imediatamente
					previousTimer = roomTimers.pop(monitorItem.roomID, None)
					if previousTimer is not None:
						previousTimer.cancel()
					roomItem.Sensor(command)
					roomItem.CommandActuators(AC_DESLIGAR)
		lst = '------------------------------------------------------\n'
		for roomID, roomItem in GetRoomDict().items():
			roomLampList = roomItem.toString()
			if roomLampList != None:
				lst = lst + roomLampList + '\n'
		lst = lst + '------------------------------------------------------\n'
		print(lst)
