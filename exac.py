import os
import re
import pymongo
import gzip
from parsing import get_variants_from_sites_vcf, get_genes_from_gencode_gtf
import lookups
import xbrowse
import copy
#from xbrowse.annotation.vep_annotations import get_vep_annotations_from_vcf

from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash


app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DB_HOST='localhost',
    DB_PORT=27017, 
    DB_NAME='exac', 
    DEBUG = True,
    SECRET_KEY = 'development key',

    SITES_VCF = os.path.join(os.path.dirname(__file__), '../exac_chr20.vcf.gz'), 
    GENCODE_GTF = os.path.join(os.path.dirname(__file__), '../gencode.v19.annotation.gtf.gz'),

))


def connect_db():
    """
    Connects to the specific database.
    """
    client = pymongo.MongoClient(host=app.config['DB_HOST'], port=app.config['DB_PORT'])
    return client[app.config['DB_NAME']]


def load_db():
    """
    Load the database
    """
    db = get_db()

    # Initialize database 
    # Don't need to explicitly create tables with mongo, just indices
    db.variants.remove()
    db.genes.remove()
    db.variants.ensure_index('xpos')
    db.genes.ensure_index('gene_id')
    db.genes.ensure_index('gene_name')

    # grab variants from sites VCF
    sites_vcf = gzip.open(app.config['SITES_VCF'])
    size = os.path.getsize(app.config['SITES_VCF'])
    progress = xbrowse.utils.get_progressbar(size, 'Loading Variants')
    for variant in get_variants_from_sites_vcf(sites_vcf):
        db.variants.insert(variant)
        try: 
            progress.update(sites_vcf.fileobj.tell())
        except IOError:  # this breaks on screwy zlib installations (ie. mac)
            pass

    # grab genes from GTF
    gtf_file = gzip.open(app.config['GENCODE_GTF'])
    size = os.path.getsize(app.config['GENCODE_GTF'])
    progress = xbrowse.utils.get_progressbar(size, 'Loading Genes')
    for gene in get_genes_from_gencode_gtf(gtf_file):
        db.genes.insert(gene)
        try: 
            progress.update(gtf_file.fileobj.tell())
        except IOError:  
            pass

def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'db_conn'):
        g.db_conn = connect_db()
    return g.db_conn


# @app.teardown_appcontext
# def close_db(error):
#     """Closes the database again at the end of the request."""
#     if hasattr(g, 'db_conn'):
#         g.db_conn.close()


@app.route('/')
def homepage():
    db = get_db()
    return render_template('homepage.html')


@app.route('/awesome')
def awesome():
    db = get_db()
    query = request.args.get('query')
    datatype, identifier = lookups.get_awesomebar_result(db, query)
    print datatype, identifier
    if datatype == 'gene':
        return redirect('/gene/{}'.format(identifier))


@app.route('/variant/<variant_str>')
def variant_page(variant_str):
    db = get_db()
    try:
        chrom, pos, ref, alt = variant_str.split('-')
        pos = int(pos)
    except ValueError:
        abort(404)
    xpos = xbrowse.get_xpos(chrom, pos)
    variant = lookups.get_variant(db, xpos, ref, alt)
    return render_template('variant.html', variant=variant)


@app.route('/gene/<gene_id>')
def gene_page(gene_id):
    db = get_db()
    gene = lookups.get_gene(db, gene_id)
    return render_template('gene.html', gene=gene)


@app.route('/howtouse')
def howtouse_page():
    return render_template('howtouse.html')


@app.route('/downloads')
def downloads_page():
    return render_template('downloads.html')


@app.route('/contact')
def contact_page():
    return render_template('contact.html')


if __name__ == "__main__":
    app.run()