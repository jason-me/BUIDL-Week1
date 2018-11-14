import hashlib



def get_proof(header, nonce):
    preimage = f"{header}:{nonce}".encode()
    proof_hex = hashlib.sha256(preimage).hexdigest()
    return int(proof_hex, 16)

'''def mine(header, target):
    nonce = 0
    while get_proof(header, nonce) >= target:
        nonce += 1 #new guess
    return nonce'''

if __name__ == "__main__":
    header = "hello"
    difficulty_bits = 4
    target = 2 ** (256 - difficulty_bits)
    for nonce in range(10):
        proof = get_proof(header, nonce)
        print(proof)
        print(f"4 bits of proof? {proof < target}")
