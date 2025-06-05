import os

print("Diretório atual:", os.getcwd())
print("Conteúdo do diretório atual:")
print(os.listdir())

print("\nConteúdo de 'projetoDjango':")
print(os.listdir("projetoDjango"))
