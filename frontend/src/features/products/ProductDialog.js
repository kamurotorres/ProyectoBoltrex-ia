import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DEFAULT_PRICE_LIST } from '@/features/products/pricing';

// Extraído de Products.js (mantenimiento fase 5) sin cambios en el JSX.
export default function ProductDialog({ activeLists, availableLists, categories, dialogOpen, editMode, formData, handleAddPrice, handleCloseDialog, handleOpenDialog, handlePriceChange, handleRemovePrice, handleSubmit, isInactiveList, isSubmitting, priceLists, setDialogOpen, setFormData }) {
  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogTrigger asChild>
        <Button onClick={() => handleOpenDialog()} data-testid="create-product-button">
          <Plus className="h-4 w-4 mr-2" />
          Nuevo Producto
        </Button>
      </DialogTrigger>
    <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="product-dialog">
      <DialogHeader>
        <DialogTitle>{editMode ? 'Editar Producto' : 'Nuevo Producto'}</DialogTitle>
        <DialogDescription>
          {editMode ? 'Modifica los datos del producto' : 'Crea un nuevo producto en el catálogo'}
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit}>
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="barcode">Código de Barras *</Label>
              <Input
                id="barcode"
                value={formData.barcode}
                onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                required
                disabled={editMode}
                data-testid="product-barcode-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Nombre *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                data-testid="product-name-input"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Descripción</Label>
            <Input
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              data-testid="product-description-input"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="category">Categoría *</Label>
              <Select
                value={formData.category}
                onValueChange={(value) => setFormData({ ...formData, category: value })}
                required
              >
                <SelectTrigger data-testid="product-category-select">
                  <SelectValue placeholder="Seleccionar" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((cat) => (
                    <SelectItem key={cat.name} value={cat.name}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="purchase_price">Precio Compra *</Label>
              <Input
                id="purchase_price"
                type="number"
                step="0.01"
                min="0"
                value={formData.purchase_price}
                onChange={(e) => setFormData({ ...formData, purchase_price: e.target.value })}
                required
                data-testid="product-purchase-price-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="tax_rate">IVA (%) *</Label>
              <Input
                id="tax_rate"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={formData.tax_rate}
                onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value })}
                required
                data-testid="product-tax-rate-input"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="min_stock">Stock mínimo (opcional)</Label>
            <Input
              id="min_stock"
              type="number"
              step="1"
              min="0"
              placeholder="Usa el general de Config. Sistema"
              value={formData.min_stock}
              onChange={(e) => setFormData({ ...formData, min_stock: e.target.value })}
              data-testid="product-min-stock-input"
            />
            <p className="text-xs text-muted-foreground">Avisa «bajo stock» cuando quedan menos unidades que este número.</p>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <div>
                <Label>Precios de Venta *</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  El precio <span className="font-mono">default</span> es obligatorio y se cobra a clientes cuya lista no tenga precio.
                  Cada precio debe ser mayor o igual al precio de compra.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddPrice}
                disabled={availableLists.length === 0}
                title={availableLists.length === 0 ? `Ya agregaste todas las listas de precios activas (${activeLists.length})` : undefined}
                data-testid="add-price-button"
              >
                <Plus className="h-3 w-3 mr-1" />
                Agregar Precio ({formData.prices.filter((p) => !isInactiveList(p.price_list_name)).length}/{activeLists.length})
              </Button>
            </div>
            {formData.prices.map((price, index) => {
              const isDefault = price.price_list_name === DEFAULT_PRICE_LIST && index === 0;
              const inactive = isInactiveList(price.price_list_name);
              // Opciones: la lista de esta fila + las activas que no usa ninguna otra fila.
              const options = [
                ...(price.price_list_name ? [priceLists.find((pl) => pl.name === price.price_list_name) || { name: price.price_list_name }] : []),
                ...availableLists,
              ];
              return (
                <div key={`${index}-${price.price_list_name}`} className="flex gap-2 items-center" data-testid={`price-row-${index}`}>
                  {isDefault ? (
                    <div className="flex h-9 w-full items-center rounded-md border border-input bg-muted/40 px-3 text-sm" title="Obligatoria: se cobra a clientes cuya lista no tenga precio">
                      default <span className="ml-1 text-xs text-muted-foreground">(obligatoria)</span>
                    </div>
                  ) : (
                    <Select
                      value={price.price_list_name}
                      onValueChange={(value) => handlePriceChange(index, 'price_list_name', value)}
                    >
                      <SelectTrigger data-testid={`price-list-select-${index}`}>
                        <SelectValue placeholder="Lista de Precios" />
                      </SelectTrigger>
                      <SelectContent>
                        {options.map((pl) => (
                          <SelectItem key={pl.name} value={pl.name} disabled={pl.is_active === false && pl.name !== price.price_list_name}>
                            {pl.name}{pl.is_active === false ? ' (inactiva)' : ''}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="Precio"
                    value={price.price}
                    onChange={(e) => handlePriceChange(index, 'price', e.target.value)}
                    data-testid={`price-input-${index}`}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemovePrice(index)}
                    disabled={isDefault}
                    title={isDefault ? 'La lista default es obligatoria' : inactive ? 'Lista inactiva: puedes quitar este precio' : 'Quitar precio'}
                    className={isDefault ? 'invisible' : ''}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
            {formData.prices.some((p) => isInactiveList(p.price_list_name)) && (
              <p className="text-xs text-amber-500" data-testid="inactive-price-note">
                Hay precios en listas inactivas: se conservan, pero no se cobran mientras la lista siga inactiva. Puedes quitarlos.
              </p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={handleCloseDialog}>
            Cancelar
          </Button>
          <Button type="submit" disabled={isSubmitting} data-testid="save-product-button">
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {editMode ? 'Actualizando...' : 'Creando...'}
              </>
            ) : (
              editMode ? 'Actualizar' : 'Crear'
            )}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
        </Dialog>
  );
}
