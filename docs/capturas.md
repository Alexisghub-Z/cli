# Capturas de la interfaz

Generadas con `python docs/generar_capturas.py` (`Console(record=True).export_text()`), sin Ollama ni terminal real. El texto plano pierde los colores: en la terminal Bruma tiene el cuerpo azul marino, el contorno azul claro y los ojos blancos.

## Bruma: las cinco expresiones

```text
normal:
      •     
   ╭──┴──╮  
  ╭╯ ● ● ╰╮ 
  │   ◡   │ 
  ╰───────╯~

pensando:
      • ... 
   ╭──┴──╮  
  ╭╯  ● ●╰╮ 
  │   ·   │ 
  ╰───────╯~

feliz:
      •     
   ╭──┴──╮  
  ╭╯ ^ ^ ╰╮ 
  │   ▽   │ 
  ╰───────╯~

preocupado:
      •     
   ╭──┴──╮  
  ╭╯ ó ò ╰╮ 
  │   ~   │ 
  ╰───────╯~

preguntando:
      • ?   
   ╭──┴──╮  
  ╭╯ ● ◕ ╰╮ 
  │   o   │ 
  ╰───────╯~
```

## Bruma en modo ASCII (terminal sin Unicode o con NO_COLOR)

```text
normal:
      o     
   .--+--.  
  .' o o '. 
  |   u   | 
  '-------'~

pensando:
      o ... 
   .--+--.  
  .'  o o'. 
  |   .   | 
  '-------'~

feliz:
      o     
   .--+--.  
  .' ^ ^ '. 
  |   w   | 
  '-------'~

preocupado:
      o     
   .--+--.  
  .' o o '. 
  |   ~   | 
  '-------'~

preguntando:
      o ?   
   .--+--.  
  .' o O '. 
  |   o   | 
  '-------'~
```

## Bienvenida

```text

      •                                                   
   ╭──┴──╮                                                
  ╭╯ ● ● ╰╮   ¡Hola! Soy Bruma, te ayudo con tus archivos.
  │   ◡   │                                               
  ╰───────╯~                                              

╭─ Puedes pedirme, por ejemplo ────────────────────────────────────────────────╮
│                                                                              │
│   1  ¿Qué archivos pesan más en Descargas?                                   │
│   2  Ordena mi carpeta de Descargas por tipo                                 │
│   3  ¿Cuánto espacio libre tengo?                                            │
│   4  Busca los PDF de esta semana                                            │
│   5  Comprime mi carpeta de Documentos                                       │
│                                                                              │
│  Escribe el número o pídemelo con tus palabras.                              │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
qwen3:8b  ·  ● conectado

ayuda  ·  deshacer  ·  limpiar  ·  salir
›
```

## Pensando (un fotograma de la animación)

```text
→ ¿Qué archivos pesan más en Descargas?
🔍 Buscando en Downloads...
      • ..                        
   ╭──┴──╮    Pensando..   7 s    
  ╭╯  ● ●╰╮   Ctrl+C para cancelar
  │   ·   │                       
  ╰───────╯~
```

## Resultado con tabla (más de 15 filas)

```text
✓ 22 archivos en ~/Downloads (9.6 GB en total)

Nombre                         ┃   Tamaño ┃       Fecha
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━
📄 ubuntu-24.04-desktop.iso    │   5.7 GB │ 21 sep 2026
📄 Proyecto final (video).mp4  │   1.7 GB │ hace 3 días
📄 fotos-vacaciones.zip        │ 898.4 MB │ 19 oct 2026
📄 instalador-zoom.pkg         │ 297.5 MB │        ayer
📄 Presentación hackathon.pptx │  46.3 MB │         hoy
📄 factura-01.pdf              │ 206.1 KB │        ayer
📄 factura-02.pdf              │ 207.0 KB │ hace 2 días
📄 factura-03.pdf              │ 208.0 KB │ hace 3 días
📄 factura-04.pdf              │ 209.0 KB │ hace 4 días
📄 factura-05.pdf              │ 210.0 KB │ hace 5 días
📄 factura-06.pdf              │ 210.9 KB │ hace 6 días
📄 factura-07.pdf              │ 211.9 KB │ 24 oct 2026
📄 factura-08.pdf              │ 212.9 KB │ 23 oct 2026
📄 factura-09.pdf              │ 213.9 KB │ 22 oct 2026
📄 factura-10.pdf              │ 214.8 KB │ 21 oct 2026
…y 7 más


      •       ╭────────────────────────────────────────────────────────────────╮
   ╭──┴──╮    │  Lo que más pesa en Descargas es la imagen de Ubuntu (5.7 GB)  │
  ╭╯ ^ ^ ╰╮   │  y el video del proyecto (1.7 GB). Si ya no los usas, puedo    │
  │   ▽   │   │  mandarlos a la papelera.                                      │
  ╰───────╯~  ╰────────────────────────────────────────────────────────────────╯
```

## Confirmación de un plan (respondiendo «n»)

```text

              ╭─ Esto es lo que haría (3 pasos) ──────────────────╮
              │                                                   │
              │  Ordenar Descargas en carpetas por tipo           │
              │                                                   │
              │  1. Crear una carpeta                             │
      • ?     │     + Carpeta nueva: ~/Downloads/PDF              │
   ╭──┴──╮    │                                                   │
  ╭╯ ● ◕ ╰╮   │  2. Mover                                         │
  │   o   │   │     → factura-01.pdf a ~/Downloads/PDF/           │
  ╰───────╯~  │                                                   │
              │  3. Mandar a la papelera                          │
              │     - instalador-zoom.pkg (312 MB) a la papelera  │
              │       ⚠ Lo puedes recuperar con «deshacer».       │
              │                                                   │
              ╰───────────────────────────────────────────────────╯
¿Lo hago? [s/N] n

      •                                 
   ╭──┴──╮                              
  ╭╯ ● ● ╰╮   De acuerdo, no toqué nada.
  │   ◡   │                             
  ╰───────╯~
```

## Error

```text

      •       ╭─ No pude hacerlo ──────────────────────────────────────────────╮
   ╭──┴──╮    │  No puedo modificar «/etc/hosts»: pertenece al sistema         │
  ╭╯ ó ò ╰╮   │  operativo.                                                    │
  │   ~   │   │                                                                │
  ╰───────╯~  │  Prueba a decirlo de otra forma, o escribe «ayuda».            │
              ╰────────────────────────────────────────────────────────────────╯
```

## Sin Ollama

```text

      •                                                     
   ╭──┴──╮                                                  
  ╭╯ ó ò ╰╮   No puedo hablar con Ollama, que es mi cerebro.
  │   ~   │                                                 
  ╰───────╯~                                                

╭─ Cómo arreglarlo ────────────────────────────────────────────────────────────╮
│                                                                              │
│  1. Abre la app de Ollama, o en otra terminal escribe:                       │
│     ollama serve                                                             │
│  2. Si es la primera vez, descarga el modelo:                                │
│     ollama pull qwen3:8b                                                     │
│  3. Vuelve aquí y pídeme algo: lo intento de nuevo.                          │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
qwen3:8b  ·  ● sin conexión
```

## Entrada sin sentido

```text
      • ?     Mmm, no te entendí. Prueba con algo como:
   ╭──┴──╮    «Comprime mi carpeta de Documentos»      
  ╭╯ ● ◕ ╰╮                                            
  │   o   │   O escribe un número del 1 al 5.          
  ╰───────╯~
```

## Despedida

```text

      •                                                     
   ╭──┴──╮                                                  
  ╭╯ ^ ^ ╰╮   ¡Hasta luego! Aquí estaré cuando me necesites.
  │   ▽   │                                                 
  ╰───────╯~
```

## Bienvenida en modo ASCII

```text

      o                                                   
   .--+--.                                                
  .' o o '.   ¡Hola! Soy Bruma, te ayudo con tus archivos.
  |   u   |                                               
  '-------'~                                              

+- Puedes pedirme, por ejemplo ------------------------------------------------+
|                                                                              |
|   1  ¿Qué archivos pesan más en Descargas?                                   |
|   2  Ordena mi carpeta de Descargas por tipo                                 |
|   3  ¿Cuánto espacio libre tengo?                                            |
|   4  Busca los PDF de esta semana                                            |
|   5  Comprime mi carpeta de Documentos                                       |
|                                                                              |
|  Escribe el número o pídemelo con tus palabras.                              |
|                                                                              |
+------------------------------------------------------------------------------+
qwen3:8b  |  * conectado

ayuda  |  deshacer  |  limpiar  |  salir
>
```

## Terminal angosta (menos de 60 columnas)

```text

╭─ No pude hacerlo ──────────────────────────────╮
│  No puedo modificar «/etc/hosts»: pertenece    │
│  al sistema operativo.                         │
│                                                │
│  Prueba a decirlo de otra forma, o escribe     │
│  «ayuda».                                      │
╰────────────────────────────────────────────────╯
```
