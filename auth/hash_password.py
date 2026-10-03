from passlib.context import CryptContext

# Define o Bcrypt como algoritmo padrão de hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class HashPassword:
    @staticmethod
    def hash_password(password: str) -> str:
        """Gera o hash da senha em texto plano."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Compara a senha em texto plano com o hash armazenado."""
        return pwd_context.verify(plain_password, hashed_password)