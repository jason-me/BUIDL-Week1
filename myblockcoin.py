"""
BlockCoin

Usage:
  myblockcoincoin.py serve
  myblockcoincoin.py ping
  myblockcoincoin.py tx <from> <to> <amount>
  myblockcoincoin.py balance <name>

Options:
  -h --help     Show this screen.
"""

import uuid, socketserver, socket, sys, argparse, time, os, logging, threading

from docopt import docopt
from copy import deepcopy
from ecdsa import SigningKey, SECP256k1
from utils import serialize, deserialize, prepare_simple_tx

from identities import user_public_key, user_private_key, bank_public_key, bank_private_key, airdrop_tx

BLOCK_TIME = 5
NUM_BANKS = 3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)-15s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def spend_message(tx, index):
    outpoint = tx.tx_ins[index].outpoint
    return serialize(outpoint) + serialize(tx.tx_outs)


class Tx:

    def __init__(self, id, tx_ins, tx_outs):
        self.id = id
        self.tx_ins = tx_ins
        self.tx_outs = tx_outs

    def sign_input(self, index, private_key):
        message = spend_message(self, index)
        signature = private_key.sign(message)
        self.tx_ins[index].signature = signature

    def verify_input(self, index, public_key):
        tx_in = self.tx_ins[index]
        message = spend_message(self, index)
        return public_key.verify(tx_in.signature, message)

class TxIn:

    def __init__(self, tx_id, index, signature=None):
        self.tx_id = tx_id
        self.index = index
        self.signature = signature

    @property
    def outpoint(self):
        return (self.tx_id, self.index)

class TxOut:

    def __init__(self, tx_id, index, amount, public_key):
        self.tx_id = tx_id
        self.index = index
        self.amount = amount
        self.public_key = public_key

    @property
    def outpoint(self):
        return (self.tx_id, self.index)

class Block:

    def __init__(self, txns, timestamp=None, signature=None):
        if timestamp == None:
            timestamp = time.time()
        self.timestamp = timestamp
        self.signature = signature
        self.txns = txns

    @property
    def message(self):
        data = [self.timestamp, self.txns]
        return serialize(data)


    def sign(self, private_key):
        self.signature = private_key.sign(self.message)

class Bank:

    def __init__(self, id, private_key):
        self.id = id
        self.private_key = private_key
        self.blocks = []
        self.utxo_set = {}
        self.mempool = []
        self.peer_addresses = {(hostname, PORT) for hostname
                               in os.environ['PEERS'].split(',')}

    @property
    def next_id(self):
        return len(self.blocks) % NUM_BANKS

    @property
    def our_turn(self):
        return self.id == self.next_id

    def update_utxo_set(self, tx):
        for tx_out in tx.tx_outs:
            self.utxo_set[tx_out.outpoint] = tx_out
        for tx_in in tx.tx_ins:
            del self.utxo_set[tx_in.outpoint]


    def validate_tx(self, tx):
        in_sum = 0
        out_sum = 0
        for index, tx_in in enumerate(tx.tx_ins):
            # TxIn spending unspent output
            assert tx_in.outpoint in self.utxo_set

            # Grab the tx_out
            tx_out = self.utxo_set[tx_in.outpoint]

            # Verify signature using public key of TxOut we're spending
            public_key = tx_out.public_key
            tx.verify_input(index, public_key)

            # Sum up the total inputs
            amount = tx_out.amount
            in_sum += amount

        for tx_out in tx.tx_outs:
            out_sum += tx_out.amount

        assert in_sum == out_sum

    def handle_tx(self, tx):
        # Save to self.utxo_set if it's valid
        self.validate_tx(tx)
        self.update_utxo_set(tx)

    def handle_block(self, block):
        # Verify bank signature
        public_key = bank_public_key(self.next_id)
        public_key.verify(block.signature, block.message)

        # Verify every transaction
        for tx in block.txns:
            self.validate_tx(tx)

        # Update self.utxo_set
        for tx in block.txns:
            self.update_utxo_set(tx)

        # Clean self.mempool HOMEWORK

        # Update self.blocks
        self.blocks.append(block)

        # Schedule next block
        self.schedule_next_block()


    def fetch_utxos(self, public_key):
        return [utxo for utxo in self.utxo_set.values()
                if utxo.public_key == public_key]

    def fetch_balance(self, public_key):
        # Fetch utxos associated with this public key
        utxos = self.fetch_utxos(public_key)
        # Sum the amounts
        return sum([tx_out.amount for tx_out in utxos])

    def make_block(self):
        txns = deepcopy(self.mempool)
        self.mempool = []
        block = Block(txns)
        block.sign(self.private_key)
        return block

    def submit_block(self):
        #Create the block
        block = self.make_block()

        # Save block locally
        self.handle_block(block)

        # Tell the other banks
        for address in self.peer_addresses:
            send_message(address, "block", block)

    def schedule_next_block(self):
        if self.our_turn:
            threading.Timer(BLOCK_TIME, self.submit_block).start()
        # TODO

    def airdrop(self, tx):
        assert len(self.blocks) == 0

         # Update self.utxo_set
        self.update_utxo_set(tx)

        # Clean self.mempool HOMEWORK

        # Update self.blocks
        block = Block([tx])
        self.blocks.append(block)

def prepare_message(command, data):
    return {
        "command": command,
        "data": data,
    }


class TCPHandler(socketserver.BaseRequestHandler):

    def respond(self, command, data):
        response = prepare_message(command, data)
        return self.request.sendall(serialize(response))

    def handle(self):
        message_bytes = self.request.recv(5000).strip()
        message = deserialize(message_bytes)
        command = message["command"]
        data = message["data"]

        logger.info(f"Received {message}")

        if command == "ping":
            self.respond(command="pong", data="")

        if command == "tx":
            try:
                bank.handle_tx(data)
                self.respond(command="tx-response", data="accepted")
            except:
                self.respond(command="tx-response", data="rejected")

        if command == "block":
            bank.handle_block(data)

        if command == "utxos":
            balance = bank.fetch_utxos(data)
            self.respond(command="utxos-response", data=balance)

        if command == "balance":
            balance = bank.fetch_balance(data)
            self.respond(command="balance-response", data=balance)


HOST, PORT = '0.0.0.0', 10000
ADDRESS = (HOST, PORT)
bank = None


def serve():
    server = socketserver.TCPServer(ADDRESS, TCPHandler)
    server.serve_forever()

def send_message(address, command, data, response=False):
    message = prepare_message(command, data)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(address)
        s.sendall(serialize(message))
        if response:
            return deserialize(s.recv(5000))

def main(args):
    if args["serve"]:
        # TODO bank == Bank(...)
        global bank
        bank_id = int(os.environ["BANK_ID"])
        bank = Bank(
            id=bank_id,
            private_key=bank_private_key(bank_id),
            )
        bank.airdrop(airdrop_tx())
        bank.schedule_next_block()
        serve()
    elif args["ping"]:
        response = send_message(ADDRESS, "ping", "", response=True)
        print(response)
    elif args["balance"]:
        name = args["<name>"]
        public_key = user_public_key(name)
        response = send_message(ADDRESS, "balance", public_key, response=True)
        print(response)
    elif args["tx"]:
        # Grab parameters
        sender_private_key = user_private_key(args["<from>"])
        sender_public_key = sender_private_key.get_verifying_key()
        recipient_private_key = user_private_key(args["<to>"])
        recipient_public_key = recipient_private_key.get_verifying_key()
        amount = int(args["<amount>"])

        # Fetch utxos available to spend
        response = send_message(ADDRESS, "utxos", sender_public_key, response=True)
        utxos = response["data"]

        # Prepare transaction
        tx = prepare_simple_tx(utxos, sender_private_key, recipient_public_key, amount)

        # send to bank
        response = send_message(ADDRESS, "tx", tx, response=True)
        print(response)
    else:
        print("Invalid commands")


if __name__ == '__main__':
    main(docopt(__doc__))
