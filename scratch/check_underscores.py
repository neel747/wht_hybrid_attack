import os
import re

tex_files = [f for f in os.listdir('.') if f.endswith('.tex')]

for fname in tex_files:
    with open(fname, 'r') as f:
        lines = f.readlines()
    
    # We want to find underscores not preceded by a backslash
    # but we should ignore listings, verbatim environments, comments, labels, and includes
    in_listing = False
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('\\begin{lstlisting}') or stripped.startswith('\\begin{verbatim}'):
            in_listing = True
        elif stripped.startswith('\\end{lstlisting}') or stripped.startswith('\\end{verbatim}'):
            in_listing = False
            continue
        
        if in_listing:
            continue
            
        # Ignore comments
        if stripped.startswith('%'):
            continue
            
        # Find all underscores
        # Look for _ not preceded by \
        # We can use regex: lookbehind assertion for no backslash
        matches = re.finditer(r'(?<!\\)_', line)
        for m in matches:
            # Check if it's inside \label{...}, \include{...}, \includeonly{...}, \input{...}, \includegraphics{...}, \bibliography{...}, \bibliographystyle{...}
            # A simple check is if the line contains these commands and the underscore is inside the braces
            # Let's print it for manual review
            print(f"{fname}:{idx}: {line.strip()}")
