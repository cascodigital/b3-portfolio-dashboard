#!/bin/bash

CSV_FILE="acoes.csv"

# Verifica se o arquivo existe
if [ ! -f "$CSV_FILE" ]; then
    echo "ticker,shares,avg_price" > "$CSV_FILE"
    echo "Arquivo $CSV_FILE criado."
fi

# Funcao para reiniciar docker
reiniciar_docker() {
    echo ""
    echo "Reiniciando Docker..."
    docker compose restart
    echo "Docker reiniciado!"
}

# Funcao para listar acoes
listar_acoes() {
    echo ""
    echo "=== ACOES ATUAIS ==="
    cat "$CSV_FILE"
    echo "===================="
    echo ""
}

# Funcao para adicionar acao
adicionar_acao() {
    echo ""
    read -p "Digite o ticker da acao: " ticker
    read -p "Digite a quantidade de acoes: " shares
    read -p "Digite o preco medio: " avg_price

    # Converte ticker para maiuscula
    ticker=$(echo "$ticker" | tr '[:lower:]' '[:upper:]')

    # Adiciona .SA se nao tiver
    if [[ ! "$ticker" =~ \.SA$ ]]; then
        ticker="${ticker}.SA"
    fi

    # Substitui virgula por ponto no preco
    avg_price=$(echo "$avg_price" | tr ',' '.')

    # Adiciona ao arquivo
    echo "${ticker},${shares},${avg_price}" >> "$CSV_FILE"

    echo ""
    echo "Acao ${ticker} adicionada com sucesso!"

    reiniciar_docker
}

# Funcao para deletar acao
deletar_acao() {
    echo ""
    echo "=== SELECIONE A ACAO PARA DELETAR ==="

    # Lista acoes com numeros (pula o header)
    linha=0
    while IFS= read -r line; do
        if [ $linha -eq 0 ]; then
            header="$line"
        else
            echo "$linha) $line"
        fi
        linha=$((linha + 1))
    done < "$CSV_FILE"

    echo ""
    read -p "Digite o numero da acao para deletar (0 para cancelar): " num

    if [ "$num" -eq 0 ]; then
        echo "Operacao cancelada."
        return
    fi

    if [ "$num" -ge 1 ] && [ "$num" -lt "$linha" ]; then
        # Cria arquivo temporario
        echo "$header" > "${CSV_FILE}.tmp"
        current=0
        while IFS= read -r line; do
            if [ $current -eq 0 ]; then
                current=$((current + 1))
                continue
            fi
            if [ $current -ne "$num" ]; then
                echo "$line" >> "${CSV_FILE}.tmp"
            fi
            current=$((current + 1))
        done < "$CSV_FILE"

        mv "${CSV_FILE}.tmp" "$CSV_FILE"
        echo ""
        echo "Acao deletada com sucesso!"

        reiniciar_docker
    else
        echo ""
        echo "Numero invalido."
    fi
}

# Loop principal
while true; do
    listar_acoes
    echo "OPCOES:"
    echo "1) Adicionar acao"
    echo "2) Deletar acao"
    echo "3) Sair"
    echo ""
    read -p "Escolha uma opcao: " opcao

    case $opcao in
        1)
            adicionar_acao
            ;;
        2)
            deletar_acao
            ;;
        3)
            echo "Saindo..."
            exit 0
            ;;
        *)
            echo "Opcao invalida!"
            ;;
    esac
done
