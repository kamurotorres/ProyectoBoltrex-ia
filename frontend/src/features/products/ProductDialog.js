import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DEFAULT_PRICE_LIST } from '@/features/products/pricing';
import { FieldError, SelectField, TextField } from '@/components/form/Field';
import { cn } from '@/lib/utils';

// Extraído de Products.js (mantenimiento fase 5). Fase 6: campos con react-hook-form (`form`) y el error de
// cada campo debajo; los precios siguen manejándose con los mismos handlers de Products.js.
export default function ProductDialog({ activeLists, availableLists, categories, dialogOpen, editMode, form, formData, handleAddPrice, handleCloseDialog, handleOpenDialog, handlePriceChange, handleRemovePrice, handleSubmit, isInactiveList, isSubmitting, priceLists, setDialogOpen }) {
  const priceErrors = form.errors.prices;
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
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <TextField form={form} name="barcode" label="Código de Barras *" disabled={editMode} data-testid="product-barcode-input" />
            <TextField form={form} name="name" label="Nombre *" data-testid="product-name-input" />
          </div>

          <TextField form={form} name="description" label="Descripción" data-testid="product-description-input" />

          <div className="grid grid-cols-3 gap-4">
            <SelectField form={form} name="category" label="Categoría *" placeholder="Seleccionar" triggerTestId="product-category-select"
                         options={categories.map((cat) => ({ value: cat.name, label: cat.name }))} />
            <TextField form={form} name="purchase_price" label="Precio Compra *" type="number" step="0.01" min="0"
                       registerOptions={{ deps: ['prices'] }}
                       data-testid="product-purchase-price-input" />
            <TextField form={form} name="tax_rate" label="IVA (%) *" type="number" step="0.01" min="0" max="100"
                       data-testid="product-tax-rate-input" />
          </div>

          <TextField form={form} name="min_stock" label="Stock mínimo (opcional)" type="number" step="1" min="0"
                     placeholder="Usa el general de Config. Sistema"
                     hint="Avisa «bajo stock» cuando quedan menos unidades que este número." data-testid="product-min-stock-input" />

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
              const rowError = priceErrors?.[index]?.price_list_name || priceErrors?.[index]?.price;
              return (
                <div key={`${index}-${price.price_list_name}`} className="space-y-1">
                <div className="flex gap-2 items-center" data-testid={`price-row-${index}`}>
                  {isDefault ? (
                    <div className="flex h-9 w-full items-center rounded-md border border-input bg-muted/40 px-3 text-sm" title="Obligatoria: se cobra a clientes cuya lista no tenga precio">
                      default <span className="ml-1 text-xs text-muted-foreground">(obligatoria)</span>
                    </div>
                  ) : (
                    <Select
                      value={price.price_list_name}
                      onValueChange={(value) => handlePriceChange(index, 'price_list_name', value)}
                    >
                      <SelectTrigger data-testid={`price-list-select-${index}`}
                                     className={cn(priceErrors?.[index]?.price_list_name && 'border-destructive')}>
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
                    aria-invalid={!!priceErrors?.[index]?.price}
                    className={cn(priceErrors?.[index]?.price && 'border-destructive')}
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
                <FieldError error={rowError} id={`price-error-${index}`} />
                </div>
              );
            })}
            <FieldError error={priceErrors?.root} id="prices-error" />
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
