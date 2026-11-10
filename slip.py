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
        # Constrói um Enlace para cada linha serial
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
        # Encontra o Enlace capaz de alcançar next_hop e envia por ele
        self.enlaces[next_hop].enviar(datagrama)

    def _callback(self, datagrama):
        if self.callback:
            self.callback(datagrama)


class Enlace:
    def __init__(self, linha_serial):
        self.linha_serial = linha_serial
        self.linha_serial.registrar_recebedor(self.__raw_recv)
        self.buffer = bytearray()

    def registrar_recebedor(self, callback):
        self.callback = callback

    def enviar(self, datagrama):
        # Passo 1 e Passo 2:
        # 1. Substituir 0xDB por 0xDB 0xDD primeiro para não corromper sub-sequências.
        # 2. Substituir 0xC0 por 0xDB 0xDC nos dados.
        dados_tratados = datagrama.replace(b'\xdb', b'\xdb\xdd')
        dados_tratados = dados_tratados.replace(b'\xc0', b'\xdb\xdc')

        # Insere o delimitador 0xC0 no início e no fim do quadro (Passo 1)
        quadro = b'\xc0' + dados_tratados + b'\xc0'

        self.linha_serial.enviar(quadro)

    def __raw_recv(self, dados):
        # Passo 3: Acumula os bytes recebidos no buffer de retenção
        self.buffer.extend(dados)

        # Processa enquanto houver delimitadores 0xC0 (fim de quadro) no buffer
        while b'\xc0' in self.buffer:
            # Retira o primeiro quadro completo até o 0xC0
            quadro_bruto, self.buffer = self.buffer.split(b'\xc0', 1)

            # Descarta datagramas vazios (gerados por 0xC0 no início ou consecutivos)
            if not quadro_bruto:
                continue

            # Passo 4: Desfaz as sequências de escape na ordem inversa
            datagrama = quadro_bruto.replace(b'\xdb\xdc', b'\xc0')
            datagrama = datagrama.replace(b'\xdb\xdd', b'\xdb')

            # Passo 5: Trata exceções no callback para evitar lixo residual
            try:
                if self.callback:
                    self.callback(datagrama)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                # O split() já removeu o quadro atual de self.buffer,
                # garantindo a limpeza completa caso o callback lance um erro.
                pass
