#!/bin/bash
# PhishTrack Database Migration Helper
# Usage: ./migrate.sh [command] [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to backend directory
cd "$(dirname "$0")"

case "$1" in
  upgrade|up)
    echo -e "${GREEN}Upgrading database to ${2:-head}...${NC}"
    alembic upgrade ${2:-head}
    echo -e "${GREEN}✓ Upgrade complete${NC}"
    ;;
    
  downgrade|down)
    echo -e "${YELLOW}⚠ Rolling back database by ${2:-1} revision(s)...${NC}"
    read -p "Are you sure? This may result in data loss. (y/N) " confirm
    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
      alembic downgrade ${2:--1}
      echo -e "${GREEN}✓ Downgrade complete${NC}"
    else
      echo -e "${RED}Cancelled${NC}"
      exit 1
    fi
    ;;
    
  generate|gen|new)
    if [ -z "$2" ]; then
      echo -e "${RED}Error: Please provide a migration description${NC}"
      echo "Usage: ./migrate.sh generate \"description\""
      exit 1
    fi
    echo -e "${GREEN}Generating new migration: $2${NC}"
    alembic revision --autogenerate -m "$2"
    echo -e "${GREEN}✓ Migration created${NC}"
    ;;
    
  current|status)
    echo -e "${GREEN}Current migration status:${NC}"
    alembic current
    ;;
    
  history|log)
    echo -e "${GREEN}Migration history:${NC}"
    alembic history -v
    ;;
    
  heads)
    echo -e "${GREEN}Head revisions:${NC}"
    alembic heads
    ;;
    
  stamp)
    if [ -z "$2" ]; then
      echo -e "${RED}Error: Please provide a revision to stamp${NC}"
      echo "Usage: ./migrate.sh stamp head"
      exit 1
    fi
    echo -e "${YELLOW}Stamping database with revision: $2${NC}"
    alembic stamp $2
    echo -e "${GREEN}✓ Database stamped${NC}"
    ;;
    
  *)
    echo "PhishTrack Database Migration Helper"
    echo ""
    echo "Usage: ./migrate.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  upgrade [rev]     Apply migrations (default: head)"
    echo "  downgrade [rev]   Rollback migrations (default: -1)"
    echo "  generate \"desc\"   Create new migration with autogenerate"
    echo "  current           Show current revision"
    echo "  history           Show migration history"
    echo "  heads             Show head revisions"
    echo "  stamp <rev>       Mark database at specific revision"
    echo ""
    echo "Examples:"
    echo "  ./migrate.sh upgrade"
    echo "  ./migrate.sh downgrade -1"
    echo "  ./migrate.sh generate \"add user preferences\""
    echo "  ./migrate.sh stamp head"
    ;;
esac
