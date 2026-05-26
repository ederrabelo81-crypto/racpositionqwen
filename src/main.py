"""
RAC Price Monitor - Main Entry Point
Orquestrador principal do sistema de scraping.
"""
import asyncio
import argparse
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import csv

from loguru import logger
from rich.console import Console
from rich.table import Table

from src.config import (
    get_scraper_config,
    KeywordsManager,
    PriorityLevel,
)
from src.scraper import SCRAPER_REGISTRY
from src.scraper.pool import get_browser_pool
from src.scraper.base import ProductRecord


console = Console()


def setup_logging():
    """Configura logging rotativo"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.remove()  # Remove handler default
    
    # Console output com rich
    logger.add(
        console.print,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    
    # File output rotativo
    logger.add(
        "logs/rac_scraper_{time:YYYY-MM-DD}.log",
        rotation="50 MB",
        retention="7 days",
        compression="zip",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    
    logger.info("Logging initialized")


async def run_collection(
    platforms: List[str],
    keywords: Optional[List[str]] = None,
    priority: Optional[PriorityLevel] = None,
    output_csv: Optional[str] = None,
) -> int:
    """
    Executa coleta de preços.
    
    Args:
        platforms: Lista de plataformas para coletar
        keywords: IDs de keywords específicas (None = todas ativas)
        priority: Filtra por prioridade (None = todas)
        output_csv: Caminho para arquivo CSV de saída
        
    Returns:
        Número de registros coletados
    """
    config = get_scraper_config()
    keywords_manager = KeywordsManager()
    browser_pool = get_browser_pool(config)
    
    # Inicializa pool de browsers
    await browser_pool.initialize()
    
    # Seleciona keywords
    if keywords:
        keyword_configs = [
            kw for kw in keywords_manager.get_enabled()
            if kw.id in keywords
        ]
    elif priority:
        keyword_configs = keywords_manager.get_by_priority(priority)
    else:
        keyword_configs = keywords_manager.get_enabled()
    
    if not keyword_configs:
        logger.warning("No keywords selected")
        return 0
    
    # Gera ID da coleta
    collection_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting collection {collection_id}")
    logger.info(f"Keywords: {len(keyword_configs)}, Platforms: {platforms}")
    
    all_records: List[ProductRecord] = []
    
    try:
        # Processa cada plataforma
        for platform_name in platforms:
            if platform_name not in SCRAPER_REGISTRY:
                logger.warning(f"Unknown platform: {platform_name}")
                continue
            
            scraper_class = SCRAPER_REGISTRY[platform_name]
            
            async with scraper_class() as scraper:
                scraper.set_collection_id(collection_id)
                
                # Processa cada keyword
                for kw_config in keyword_configs:
                    logger.info(f"Scraping '{kw_config.term}' on {platform_name}")
                    
                    try:
                        async for record in scraper.search(kw_config.term):
                            all_records.append(record)
                            
                            # Progress indicator
                            if len(all_records) % 50 == 0:
                                logger.info(f"Collected {len(all_records)} records so far...")
                    
                    except Exception as e:
                        logger.error(f"Error scraping keyword '{kw_config.term}': {e}")
                        continue
                    
                    # Delay entre keywords
                    await asyncio.sleep(config.MIN_DELAY)
    
    finally:
        # Shutdown browser pool
        await browser_pool.shutdown()
    
    # Exporta resultados
    logger.info(f"Collection complete: {len(all_records)} records")
    
    if output_csv:
        await export_to_csv(all_records, output_csv)
        logger.info(f"Results exported to {output_csv}")
    
    # Stats do pool
    stats = browser_pool.get_stats()
    logger.info(f"Browser pool stats: {stats}")
    
    return len(all_records)


async def export_to_csv(records: List[ProductRecord], filepath: str):
    """Exporta registros para CSV UTF-8 BOM"""
    
    if not records:
        return
    
    # Converte para dicts
    rows = [r.to_supabase_dict() for r in records]
    
    # Campo names
    fieldnames = list(rows[0].keys())
    
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def show_status():
    """Mostra status do sistema"""
    keywords_manager = KeywordsManager()
    config = get_scraper_config()
    
    table = Table(title="RAC Price Monitor Status")
    table.add_column("Component", style="cyan")
    table.add_column("Value", style="green")
    
    # Keywords
    all_kws = keywords_manager.get_all()
    enabled_kws = keywords_manager.get_enabled()
    table.add_row("Total Keywords", str(len(all_kws)))
    table.add_row("Enabled Keywords", str(len(enabled_kws)))
    
    # Prioridades
    for priority in PriorityLevel:
        count = len(keywords_manager.get_by_priority(priority))
        table.add_row(f"Keywords ({priority.value})", str(count))
    
    # Config
    table.add_row("Max Browsers", str(config.MAX_BROWSERS))
    table.add_row("Max Pages/Keyword", str(config.MAX_PAGES))
    table.add_row("Headless", str(config.HEADLESS))
    
    # Platforms
    table.add_row("Available Platforms", ", ".join(SCRAPER_REGISTRY.keys()))
    
    console.print(table)


async def main_async(args):
    """Main function async"""
    
    if args.status:
        show_status()
        return
    
    platforms = args.platforms if args.platforms else ['mercado_livre', 'dealers']
    
    priority = None
    if args.priority:
        try:
            priority = PriorityLevel(args.priority)
        except ValueError:
            console.print(f"[red]Invalid priority: {args.priority}[/red]")
            return
    
    records_count = await run_collection(
        platforms=platforms,
        keywords=args.keywords,
        priority=priority,
        output_csv=args.output,
    )
    
    console.print(f"\n[green]✓ Collection complete: {records_count} records[/green]")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="RAC Price Monitor - Coleta de preços de ar condicionado"
    )
    
    parser.add_argument(
        '--platforms', '-p',
        nargs='+',
        choices=list(SCRAPER_REGISTRY.keys()) + ['all'],
        help="Plataformas para coletar"
    )
    
    parser.add_argument(
        '--keywords', '-k',
        nargs='+',
        help="IDs de keywords específicas"
    )
    
    parser.add_argument(
        '--priority',
        choices=['alta', 'media', 'baixa'],
        help="Filtra keywords por prioridade"
    )
    
    parser.add_argument(
        '--output', '-o',
        help="Arquivo CSV de saída"
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help="Mostra status do sistema"
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help="Coleta completa em todas plataformas"
    )
    
    args = parser.parse_args()
    
    # Handle --all flag
    if args.all:
        args.platforms = list(SCRAPER_REGISTRY.keys())
    
    setup_logging()
    
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
