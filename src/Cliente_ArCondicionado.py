#####################################################
#                                                   #
# Título do trabalho: Trabalho de Sockets           #
#         Disciplina: Redes de Computadores PPComp  #
#                                                   #
# Cliente do novo dispositivo: Ar-Condicionado      #
# Inteligente (tipo 4, código 'A')                  #
#                                                   #
#####################################################

from Config import *
from Message import *
from ClientUtil import *
import socket

deviceID = None

####################
# Inicializando... #
####################
if __name__ == '__main__':
	print('Inicializando cliente: Ar-Condicionado Inteligente...')
	try:
		connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		destination = (SERVIDOR, PORTA)
		connection.connect(destination)
	except:
		print(f'Falha ao tentar se conectar com o servidor {SERVIDOR} porta {PORTA}')
		exit()
	# Registra o dispositivo informando o tipo de Ar-Condicionado Inteligente
	device = Device(connection, NUM_AR_CONDICIONADO)
	print(f'Enviando solicitação de registro (tipo {NUM_AR_CONDICIONADO})...')
	roomDict = ClientRegister(device)
	if roomDict != None:
		deviceID, roomID, roomName = SelectRoom(device, roomDict)
		if deviceID != None:
			while True:
				print(f'\n==> Ambiente [{roomID}] {roomName}')
				msg = ReceiveMessage(connection, device)
				if msg is None:
					print('Servidor encerrou a conexão.')
					break
				if(msg.code == MSG_AR_CONDICIONADO):
					print('Comando recebido do servidor!!!')
					print('#####################################')
					if msg.action == AC_LIGAR:
						print(f'       AR-CONDICIONADO LIGADO')
						print(f'    Temperatura alvo: {msg.value}°C')
					elif msg.action == AC_DESLIGAR:
						print(f'       AR-CONDICIONADO DESLIGADO')
					else:
						print(f'Ação inválida: {msg.action}')
					print('#####################################')
					msg = MessageStatus()
					connection.send(msg.pack(deviceID, ACAO_EXECUTADA))
				else:
					print('Mensagem inválida code:', msg.code)
	connection.close()