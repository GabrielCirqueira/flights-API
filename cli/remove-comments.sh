#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN=false
USE_DIFF=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --diff)    USE_DIFF=true ;;
    *) echo "Flag desconhecida: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v perl >/dev/null 2>&1; then
  echo "perl não encontrado." >&2
  exit 1
fi

if $USE_DIFF; then
  if ! git -C "$ROOT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    echo "Não é um repositório git." >&2
    exit 1
  fi
  echo "Modo: arquivos staged (git diff --cached)"
  mapfile -t FILES < <(
    git -C "$ROOT_DIR" diff --cached --name-only \
      | while read -r f; do
          full="$ROOT_DIR/$f"
          [[ -f "$full" && "$f" == *.py ]] && echo "$full"
        done \
      | sort
  )
else
  echo "Modo: pasta app/ (*.py)"
  mapfile -t FILES < <(
    find "$ROOT_DIR/app" \
      -name "*.py" \
      -not -path "*/.venv/*" \
      -not -path "*/__pycache__/*" \
      -not -path "*/.git/*" \
      | sort
  )
fi

changed=0

for FILE in "${FILES[@]}"; do
  ORIG=$(<"$FILE")
  EXT="${FILE##*.}"

  case "$EXT" in
    py)
      NEW=$(perl -0777 -pe '
        # Preserva shebang (primeira linha #!/...)
        s/\A(#![^\n]*\n)//; my $shebang = $1 // q{};
        # Preserva encoding cookie (# -*- coding: ... -*-)
        s/\A((?:\#[^\n]*coding[^\n]*\n)+)//; my $encoding = $1 // q{};
        while (s/^[ \t]*"""[\s\S]*?"""[ \t]*\n//m) {}
        s/^[ \t]*#[^\n]*\n//gm;
        # Comentário inline # precedido de espaço
        s/[ \t]+#[^\n]*$//gm;
        # Colapsa linhas em branco consecutivas em no máximo uma
        s/\n{3,}/\n\n/g;
        $_ = $shebang . $encoding . $_;
      ' "$FILE")
      ;;
    *)
      continue
      ;;
  esac

  if [[ "$NEW" != "$ORIG" ]]; then
    REL="${FILE#"$ROOT_DIR"/}"
    if $DRY_RUN; then
      echo "[dry-run] $REL"
    else
      printf '%s' "$NEW" > "$FILE"
      echo "  $REL"
    fi
    changed=$((changed + 1))
  fi
done

echo ""
if $DRY_RUN; then
  echo "✓ (dry-run) $changed arquivo(s) seriam alterados."
else
  echo "✓ $changed arquivo(s) alterados."
fi
