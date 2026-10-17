"""Loopback-only protocol fixtures. Messages stay in memory; no delivery or internet access."""
import base64
import ipaddress
import socketserver
import ssl
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def make_certificate(folder):
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Outreach temporary test CA")])
    now = datetime.now(timezone.utc)
    root = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    leaf = (x509.CertificateBuilder().subject_name(leaf_name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    root_path, leaf_path, key_path = [folder / filename for filename in ("ca.pem", "server.pem", "key.pem")]
    root_path.write_bytes(root.public_bytes(serialization.Encoding.PEM))
    leaf_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(leaf_path, key_path)
    return root_path, context


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    def handle_error(self, request, address):
        self.errors.append("protocol connection closed")


class Protocol(socketserver.BaseRequestHandler):
    def attach(self, connection):
        self.connection = connection
        self.connection.settimeout(5)
        self.stream = connection.makefile("rb")

    def write(self, data):
        self.connection.sendall(data)

    def line(self):
        return self.stream.readline(65536)

    def finish(self):
        if getattr(self, "stream", None):
            self.stream.close()
        if getattr(self, "connection", None):
            self.connection.close()


class SMTP(Protocol):
    def handle(self):
        server = self.server
        tls = server.mode == "ssl"
        self.attach(server.tls.wrap_socket(self.request, server_side=True) if tls else self.request)
        self.write(b"220 localhost ESMTP test fixture\r\n")
        while raw := self.line():
            command = raw.split(b" ", 1)[0].strip().upper()
            server.commands.append(command.decode())
            if command == b"EHLO":
                self.write(b"250-localhost\r\n250-AUTH PLAIN\r\n250 STARTTLS\r\n")
            elif command == b"STARTTLS":
                self.write(b"220 ready for TLS\r\n")
                self.stream.close()
                self.attach(server.tls.wrap_socket(self.connection, server_side=True))
                tls = True
            elif command == b"AUTH":
                if not tls:
                    server.errors.append("unencrypted AUTH")
                    self.write(b"538 encryption required\r\n")
                    continue
                value = base64.b64decode(raw.split()[2])
                assert value == b"\x00test\x00test"
                server.authenticated = server.behavior != "bad_login"
                self.write(b"535 bad login\r\n" if server.behavior == "bad_login" else b"235 authenticated\r\n")
            elif command in {b"MAIL", b"RSET"}:
                self.write(b"250 ok\r\n")
            elif command == b"RCPT":
                self.write(b"450 temporary recipient rejection\r\n" if server.behavior == "recipient_delay" else b"250 recipient ok\r\n")
            elif command == b"DATA":
                self.write(b"354 send message\r\n")
                lines = []
                while (line := self.line()) and line != b".\r\n":
                    lines.append(line[1:] if line.startswith(b"..") else line)
                message = b"".join(lines)
                if server.behavior == "data_reject":
                    self.write(b"554 message rejected\r\n")
                else:
                    server.messages.append(message)
                    if server.behavior == "drop_after_data":
                        return
                    self.write(b"250 accepted\r\n")
            elif command == b"QUIT":
                if server.behavior != "quit_disconnect":
                    self.write(b"221 bye\r\n")
                return
            else:
                self.write(b"500 unsupported command\r\n")


class IMAP(Protocol):
    def handle(self):
        self.attach(self.server.tls.wrap_socket(self.request, server_side=True))
        self.write(b"* OK IMAP fixture ready\r\n")
        while raw := self.line():
            fields = raw.strip().split()
            tag, command = fields[:2]
            command = command.upper()
            self.server.commands.append(command.decode())
            if command == b"CAPABILITY":
                self.write(b"* CAPABILITY IMAP4rev1\r\n" + tag + b" OK capability\r\n")
            elif command == b"LOGIN":
                self.server.authenticated = True
                self.write(tag + b" OK login\r\n")
            elif command in {b"SELECT", b"EXAMINE"}:
                self.write(b"* 1 EXISTS\r\n* OK [UIDVALIDITY 123] validity\r\n" + tag + b" OK [READ-ONLY] selected\r\n")
            elif command == b"UID" and fields[2].upper() == b"SEARCH":
                self.write(b"* SEARCH 1\r\n" + tag + b" OK search\r\n")
            elif command == b"UID" and fields[2].upper() == b"FETCH":
                payload = self.server.inbound[:65536]
                self.write(b"* 1 FETCH (UID 1 BODY[]<0> {" + str(len(payload)).encode() + b"}\r\n" +
                           payload + b")\r\n" + tag + b" OK fetch\r\n")
            elif command == b"LOGOUT":
                self.write(b"* BYE logout\r\n" + tag + b" OK logout\r\n")
                return
            else:
                self.write(tag + b" BAD unsupported command\r\n")


@contextmanager
def mail_server(tls, protocol="smtp", mode="starttls", behavior="accept", inbound=b""):
    server = Server(("127.0.0.1", 0), SMTP if protocol == "smtp" else IMAP)
    server.tls, server.mode, server.behavior, server.inbound = tls, mode, behavior, inbound
    server.messages, server.commands, server.errors = [], [], []
    server.authenticated = False
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
