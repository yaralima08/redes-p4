class CamadaEnlace:
    ignore_checksum = False

    def __init__(self, linhas_seriais):
        """
        Inicia uma camada de enlace com um ou mais enlaces, cada um conectado
        a uma linha serial distinta. O argumento linhas_seriais é um dicionário
        no formato {ip_outra_ponta: linha_serial}. O ip_outra_ponta é o IP do
        host ou roteador que se encontra na outra ponta do enlace, escrito como
        uma string no formato 'x.y.z.w'. A linha_serial é um objeto da classe
        PTY (vide camadafisica.py) ou de outra classe que implemente os métodos
        registrar_recebedor e enviar.
        """
        self.enlaces = {}
        self.callback = None
        #Constrói um Enlace para cada linha serial
        for ip_outra_ponta, linha_serial in linhas_seriais.items():
            enlace = Enlace(linha_serial)
            self.enlaces[ip_outra_ponta] = enlace
            enlace.registrar_recebedor(self._callback)

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de enlace
        """
        self.callback = callback

    def enviar(self, datagrama, next_hop):
        """
        Envia datagrama para next_hop, onde next_hop é um endereço IPv4
        fornecido como string (no formato x.y.z.w). A camada de enlace se
        responsabilizará por encontrar em qual enlace se encontra o next_hop.
        """
        #Encontra o Enlace capaz de alcançar next_hop e envia por ele
        self.enlaces[next_hop].enviar(datagrama)

    def _callback(self, datagrama):
        if self.callback:
            self.callback(datagrama)


class Enlace:
    def __init__(self, linha_serial):
        self.linha_serial = linha_serial
        self.callback = None                      #evita AttributeError se chegarem dados antes do registro
        self.buffer = bytearray()                 #dados residuais (quadro ainda incompleto) - Passo 3
        self.linha_serial.registrar_recebedor(self.__raw_recv)

    def registrar_recebedor(self, callback):
        self.callback = callback

    #Passos 1 e 2: envio 
    def enviar(self, datagrama):
        #Passo 2: sequências de escape
        #O 0xDB deve ser escapado PRIMEIRO; se fosse o 0xC0 primeiro, o 0xDB
        #inserido por ele seria escapado de novo e corromperia o quadro
        dados_tratados = datagrama.replace(b'\xdb', b'\xdb\xdd')   #0xDB -> 0xDB 0xDD
        dados_tratados = dados_tratados.replace(b'\xc0', b'\xdb\xdc')  #0xC0 -> 0xDB 0xDC

        #Passo 1: delimitador 0xC0 no início e no fim do quadro
        quadro = b'\xc0' + dados_tratados + b'\xc0'
        self.linha_serial.enviar(quadro)

    #Passos 3, 4 e 5: recepção 
    def __raw_recv(self, dados):
        #Passo 3: os bytes podem chegar quebrados ou vários quadros de uma vez,
        #então acumulamos tudo no buffer e só processamos quadros completos
        self.buffer.extend(dados)

        #Cada 0xC0 no buffer marca o fim de um quadro
        while b'\xc0' in self.buffer:
            quadro_bruto, self.buffer = self.buffer.split(b'\xc0', 1)

            #passo 3: não repassar datagramas vazios (0xC0 no início/fim do quadro)
            if not quadro_bruto:
                continue

            #passo 4: desfaz as sequências de escape (ordem inversa do envio)
            datagrama = bytes(quadro_bruto)
            datagrama = datagrama.replace(b'\xdb\xdc', b'\xc0')   # 0xDB 0xDC -> 0xC0
            datagrama = datagrama.replace(b'\xdb\xdd', b'\xdb')   # 0xDB 0xDD -> 0xDB

            #passo 5: se a camada superior lançar exceção, ignoramos o erro
            #(mostrando na tela) para o datagrama mal formado não ficar no buffer
            try:
                if self.callback:
                    self.callback(datagrama)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                #O split() já tirou o quadro atual de self.buffer, então não
                #sobra nenhum pedaço dele aqui; o que resta no buffer é só o
                #começo do PRÓXIMO quadro, que deve ser mantido
                pass
