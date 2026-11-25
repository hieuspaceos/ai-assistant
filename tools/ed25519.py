"""ed25519.py — verify + sign ed25519 thuần Python (stdlib-only).

Vendored từ public-domain reference implementation của Bernstein et al
(ed25519.cr.yp.to — slowst_reference) — chọn bản này vì nhỏ, không dep,
và đây là code mật mã đã được kiểm chứng lâu năm; KHÔNG tự viết crypto.

Chậm (~1-2s/verify) nhưng đủ: mỗi máy chỉ verify MỘT manifest mỗi lần
update. Ký chỉ xảy ra phía vendor (sign-release.py) nên cũng không cần
nhanh.

Dùng:
    from ed25519 import publickey, signature, checkvalid
    pk = publickey(seed32)                      # vendor tạo cặp khoá
    sig = signature(msg_bytes, seed32, pk)      # ký ở vendor
    checkvalid(sig, msg_bytes, pk)              # verify trên máy NV —
                                              # raise Exception nếu sai
"""
import hashlib

b = 256
q = 2 ** 255 - 19
l = 2 ** 252 + 27742317777372353535851937790883648493


def H(m):
    return hashlib.sha512(m).digest()


def expmod(bb, e, m):
    if e == 0:
        return 1
    t = expmod(bb, e // 2, m) ** 2 % m
    if e & 1:
        t = (t * bb) % m
    return t


def inv(x):
    return expmod(x, q - 2, q)


d = -121665 * inv(121666) % q
I = expmod(2, (q - 1) // 4, q)


def xrecover(y):
    xx = (y * y - 1) * inv(d * y * y + 1)
    x = expmod(xx, (q + 3) // 8, q)
    if (x * x - xx) % q != 0:
        x = (x * I) % q
    if x % 2 != 0:
        x = q - x
    return x


By = 4 * inv(5)
Bx = xrecover(By)
B = [Bx % q, By % q]


def edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * inv(1 + d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * inv(1 - d * x1 * x2 * y1 * y2)
    return [x3 % q, y3 % q]


def scalarmult(P, e):
    if e == 0:
        return [0, 1]
    Q = scalarmult(P, e // 2)
    Q = edwards(Q, Q)
    if e & 1:
        Q = edwards(Q, P)
    return Q


def encodeint(y):
    bits = [(y >> i) & 1 for i in range(b)]
    return bytes([sum([bits[i * 8 + j] << j for j in range(8)])
                  for i in range(b // 8)])


def encodepoint(P):
    x, y = P
    bits = [(y >> i) & 1 for i in range(b - 1)] + [x & 1]
    return bytes([sum([bits[i * 8 + j] << j for j in range(8)])
                  for i in range(b // 8)])


def bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def publickey(sk):
    """sk = seed 32 byte → trả public key 32 byte."""
    h = H(sk)
    a = 2 ** (b - 2) + sum(2 ** i * bit(h, i) for i in range(3, b - 2))
    A = scalarmult(B, a)
    return encodepoint(A)


def Hint(m):
    h = H(m)
    return sum(2 ** i * bit(h, i) for i in range(2 * b))


def signature(m, sk, pk):
    h = H(sk)
    a = 2 ** (b - 2) + sum(2 ** i * bit(h, i) for i in range(3, b - 2))
    r = Hint(bytes([h[j] for j in range(b // 8, b // 4)]) + m)
    R = scalarmult(B, r)
    S = (r + Hint(encodepoint(R) + pk + m) * a) % l
    return encodepoint(R) + encodeint(S)


def isoncurve(P):
    x, y = P
    return (-x * x + y * y - 1 - d * x * x * y * y) % q == 0


def decodeint(s):
    return sum(2 ** i * bit(s, i) for i in range(0, b))


def decodepoint(s):
    y = sum(2 ** i * bit(s, i) for i in range(0, b - 1))
    x = xrecover(y)
    if x & 1 != bit(s, b - 1):
        x = q - x
    P = [x, y]
    if not isoncurve(P):
        raise Exception("decoding point that is not on curve")
    return P


def checkvalid(s, m, pk):
    """Raise Exception nếu chữ ký sai; trả True nếu đúng."""
    if len(s) != b // 4:
        raise Exception("signature length is wrong")
    if len(pk) != b // 8:
        raise Exception("public-key length is wrong")
    R = decodepoint(s[:b // 8])
    A = decodepoint(pk)
    S = decodeint(s[b // 8:b // 4])
    h = Hint(s[:b // 8] + pk + m)
    if scalarmult(B, S) != edwards(R, scalarmult(A, h)):
        raise Exception("signature does not pass verification")
    return True
